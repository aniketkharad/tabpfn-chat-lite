"""State store interfaces and implementations for tabchat.

Invariants:
- Correctness must not depend on local persistent disk.
- Default runtime operates in RAM with a configurable session TTL.
- DiskStore is provided for offline testing, crash recovery simulation, and local persistence.
- GatewayStoreStub is provided for future edge gateway state synchronization.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import secrets
import shutil
import time
from typing import Any, Optional

import pandas as pd

from tabchat.config import get_settings


class SessionNotFoundError(KeyError):
    """Raised when a requested session does not exist or has expired."""


class Store(ABC):
    """Abstract interface defining session and state storage."""

    @abstractmethod
    def create_session(self, session_id: str | None = None) -> str:
        """Create a new session, returning the session ID."""

    @abstractmethod
    def session_exists(self, session_id: str) -> bool:
        """Check whether a session exists and is active (not expired)."""

    @abstractmethod
    def get_lock(self, session_id: str) -> asyncio.Lock:
        """Retrieve concurrency lock for a session."""

    @abstractmethod
    def save_dataset(self, session_id: str, file_bytes: bytes, card: dict[str, Any]) -> None:
        """Save uploaded raw CSV bytes and dataset card."""

    @abstractmethod
    def get_dataset(self, session_id: str) -> tuple[pd.DataFrame, dict[str, Any]]:
        """Retrieve parsed DataFrame and dataset card."""

    @abstractmethod
    def get_raw_bytes(self, session_id: str) -> bytes:
        """Retrieve raw CSV bytes."""

    @abstractmethod
    def append_history(self, session_id: str, role: str, message: str) -> None:
        """Append a conversational turn to session history."""

    @abstractmethod
    def get_history(self, session_id: str) -> list[dict[str, Any]]:
        """Retrieve conversational history turns."""

    @abstractmethod
    def save_job_spec(self, session_id: str, spec: dict[str, Any]) -> None:
        """Save active JobSpec."""

    @abstractmethod
    def get_job_spec(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve active JobSpec if present."""

    @abstractmethod
    def save_plan(self, session_id: str, plan: dict[str, Any]) -> None:
        """Save active Plan."""

    @abstractmethod
    def get_plan(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve active Plan if present."""

    @abstractmethod
    def save_results(self, session_id: str, results: dict[str, Any]) -> None:
        """Save execution results."""

    @abstractmethod
    def get_results(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve execution results if present."""

    @abstractmethod
    def delete_session(self, session_id: str) -> None:
        """Delete session and all associated state immediately."""

    @abstractmethod
    def prune_expired(self) -> int:
        """Remove expired sessions, returning number of pruned sessions."""


class MemoryStore(Store):
    """Default in-memory state store keeping all session artifacts in RAM with TTL."""

    def __init__(self, ttl_seconds: float = 86400.0) -> None:
        self.ttl_seconds = ttl_seconds
        # _sessions: session_id -> dict of session data
        self._sessions: dict[str, dict[str, Any]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    def _now(self) -> float:
        return time.time()

    def _require_session(self, session_id: str) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(f"Session '{session_id}' not found.")
        if self._now() > session["expires_at"]:
            self.delete_session(session_id)
            raise SessionNotFoundError(f"Session '{session_id}' has expired.")
        return session

    def create_session(self, session_id: str | None = None) -> str:
        s_id = session_id or secrets.token_hex(16)
        now = self._now()
        self._sessions[s_id] = {
            "created_at": now,
            "expires_at": now + self.ttl_seconds,
            "raw_bytes": None,
            "dataset_card": None,
            "df": None,
            "history": [],
            "job_spec": None,
            "plan": None,
            "results": None,
            "events": [],
        }
        self._locks[s_id] = asyncio.Lock()
        return s_id

    def session_exists(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session is None:
            return False
        if self._now() > session["expires_at"]:
            self.delete_session(session_id)
            return False
        return True

    def get_lock(self, session_id: str) -> asyncio.Lock:
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        return self._locks[session_id]

    def save_dataset(self, session_id: str, file_bytes: bytes, card: dict[str, Any]) -> None:
        session = self._require_session(session_id)
        session["raw_bytes"] = file_bytes
        session["dataset_card"] = card
        session["df"] = pd.read_csv(io.BytesIO(file_bytes), encoding="utf-8-sig")

    def get_dataset(self, session_id: str) -> tuple[pd.DataFrame, dict[str, Any]]:
        session = self._require_session(session_id)
        if session["df"] is None or session["dataset_card"] is None:
            raise FileNotFoundError(f"Dataset not found for session '{session_id}'.")
        return session["df"].copy(), session["dataset_card"]

    def get_raw_bytes(self, session_id: str) -> bytes:
        session = self._require_session(session_id)
        if session["raw_bytes"] is None:
            raise FileNotFoundError(f"Raw CSV bytes missing for session '{session_id}'.")
        return session["raw_bytes"]

    def append_history(self, session_id: str, role: str, message: str) -> None:
        session = self._require_session(session_id)
        record = {
            "role": role,
            "content": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        session["history"].append(record)

    def get_history(self, session_id: str) -> list[dict[str, Any]]:
        session = self._require_session(session_id)
        return list(session["history"])

    def save_job_spec(self, session_id: str, spec: dict[str, Any]) -> None:
        session = self._require_session(session_id)
        session["job_spec"] = spec

    def get_job_spec(self, session_id: str) -> dict[str, Any] | None:
        session = self._require_session(session_id)
        return session["job_spec"]

    def save_plan(self, session_id: str, plan: dict[str, Any]) -> None:
        session = self._require_session(session_id)
        session["plan"] = plan

    def get_plan(self, session_id: str) -> dict[str, Any] | None:
        session = self._require_session(session_id)
        return session["plan"]

    def save_results(self, session_id: str, results: dict[str, Any]) -> None:
        session = self._require_session(session_id)
        session["results"] = results

    def get_results(self, session_id: str) -> dict[str, Any] | None:
        session = self._require_session(session_id)
        return session["results"]

    def delete_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._locks.pop(session_id, None)

    def prune_expired(self) -> int:
        now = self._now()
        expired_ids = [s_id for s_id, s in self._sessions.items() if now > s["expires_at"]]
        for s_id in expired_ids:
            self.delete_session(s_id)
        return len(expired_ids)


class DiskStore(Store):
    """Filesystem-backed store maintaining backward-compatible POSIX directory layout."""

    def __init__(self, data_dir: Path | str) -> None:
        self.data_dir = Path(data_dir).resolve()
        self.sessions_dir = self.data_dir / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, asyncio.Lock] = {}

    def get_lock(self, session_id: str) -> asyncio.Lock:
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        return self._locks[session_id]

    def _session_dir(self, session_id: str) -> Path:
        return self.sessions_dir / session_id

    def create_session(self, session_id: str | None = None) -> str:
        s_id = session_id or secrets.token_hex(16)
        s_dir = self._session_dir(s_id)
        s_dir.mkdir(parents=True, exist_ok=True)
        return s_id

    def session_exists(self, session_id: str) -> bool:
        return self._session_dir(session_id).is_dir()

    def _require_session(self, session_id: str) -> Path:
        s_dir = self._session_dir(session_id)
        if not s_dir.is_dir():
            raise SessionNotFoundError(f"Session '{session_id}' not found.")
        return s_dir

    def save_dataset(self, session_id: str, file_bytes: bytes, card: dict[str, Any]) -> None:
        s_dir = self._require_session(session_id)
        (s_dir / "raw.csv").write_bytes(file_bytes)
        (s_dir / "dataset_card.json").write_text(
            json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def get_dataset(self, session_id: str) -> tuple[pd.DataFrame, dict[str, Any]]:
        s_dir = self._require_session(session_id)
        raw_path = s_dir / "raw.csv"
        card_path = s_dir / "dataset_card.json"
        if not raw_path.exists():
            raise FileNotFoundError(f"Dataset raw.csv not found for session '{session_id}'.")
        if not card_path.exists():
            raise FileNotFoundError(f"dataset_card.json not found for session '{session_id}'.")

        df = pd.read_csv(io.BytesIO(raw_path.read_bytes()), encoding="utf-8-sig")
        card = json.loads(card_path.read_text(encoding="utf-8"))
        return df, card

    def get_raw_bytes(self, session_id: str) -> bytes:
        s_dir = self._require_session(session_id)
        raw_path = s_dir / "raw.csv"
        if not raw_path.exists():
            raise FileNotFoundError(f"Raw CSV bytes missing for session '{session_id}'.")
        return raw_path.read_bytes()

    def append_history(self, session_id: str, role: str, message: str) -> None:
        s_dir = self._require_session(session_id)
        history_path = s_dir / "history.jsonl"
        record = {
            "role": role,
            "content": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with open(history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def get_history(self, session_id: str) -> list[dict[str, Any]]:
        s_dir = self._require_session(session_id)
        history_path = s_dir / "history.jsonl"
        if not history_path.exists():
            return []
        messages: list[dict[str, Any]] = []
        with open(history_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    messages.append(json.loads(line))
        return messages

    def save_job_spec(self, session_id: str, spec: dict[str, Any]) -> None:
        s_dir = self._require_session(session_id)
        (s_dir / "job_spec.json").write_text(
            json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def get_job_spec(self, session_id: str) -> dict[str, Any] | None:
        s_dir = self._require_session(session_id)
        spec_path = s_dir / "job_spec.json"
        if not spec_path.exists():
            return None
        return json.loads(spec_path.read_text(encoding="utf-8"))

    def save_plan(self, session_id: str, plan: dict[str, Any]) -> None:
        s_dir = self._require_session(session_id)
        (s_dir / "plan.json").write_text(
            json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def get_plan(self, session_id: str) -> dict[str, Any] | None:
        s_dir = self._require_session(session_id)
        plan_path = s_dir / "plan.json"
        if not plan_path.exists():
            return None
        return json.loads(plan_path.read_text(encoding="utf-8"))

    def save_results(self, session_id: str, results: dict[str, Any]) -> None:
        s_dir = self._require_session(session_id)
        (s_dir / "results.json").write_text(
            json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def get_results(self, session_id: str) -> dict[str, Any] | None:
        s_dir = self._require_session(session_id)
        results_path = s_dir / "results.json"
        if not results_path.exists():
            return None
        return json.loads(results_path.read_text(encoding="utf-8"))

    def delete_session(self, session_id: str) -> None:
        s_dir = self._session_dir(session_id)
        if s_dir.exists():
            shutil.rmtree(s_dir)
        self._locks.pop(session_id, None)

    def prune_expired(self) -> int:
        return 0


class GatewayStoreStub(Store):
    """Gateway-backed store stub for edge session synchronization."""

    def __init__(self, endpoint: str = "/internal/store") -> None:
        self.endpoint = endpoint
        self._fallback = MemoryStore()

    def create_session(self, session_id: str | None = None) -> str:
        return self._fallback.create_session(session_id)

    def session_exists(self, session_id: str) -> bool:
        return self._fallback.session_exists(session_id)

    def get_lock(self, session_id: str) -> asyncio.Lock:
        return self._fallback.get_lock(session_id)

    def save_dataset(self, session_id: str, file_bytes: bytes, card: dict[str, Any]) -> None:
        self._fallback.save_dataset(session_id, file_bytes, card)

    def get_dataset(self, session_id: str) -> tuple[pd.DataFrame, dict[str, Any]]:
        return self._fallback.get_dataset(session_id)

    def get_raw_bytes(self, session_id: str) -> bytes:
        return self._fallback.get_raw_bytes(session_id)

    def append_history(self, session_id: str, role: str, message: str) -> None:
        self._fallback.append_history(session_id, role, message)

    def get_history(self, session_id: str) -> list[dict[str, Any]]:
        return self._fallback.get_history(session_id)

    def save_job_spec(self, session_id: str, spec: dict[str, Any]) -> None:
        self._fallback.save_job_spec(session_id, spec)

    def get_job_spec(self, session_id: str) -> dict[str, Any] | None:
        return self._fallback.get_job_spec(session_id)

    def save_plan(self, session_id: str, plan: dict[str, Any]) -> None:
        self._fallback.save_plan(session_id, plan)

    def get_plan(self, session_id: str) -> dict[str, Any] | None:
        return self._fallback.get_plan(session_id)

    def save_results(self, session_id: str, results: dict[str, Any]) -> None:
        self._fallback.save_results(session_id, results)

    def get_results(self, session_id: str) -> dict[str, Any] | None:
        return self._fallback.get_results(session_id)

    def delete_session(self, session_id: str) -> None:
        self._fallback.delete_session(session_id)

    def prune_expired(self) -> int:
        return self._fallback.prune_expired()
