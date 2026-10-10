"""Cryptographic hash-chained event logging and LogSink interfaces for tabchat.

Invariants:
- Every event is logged in sequence with a SHA-256 hash chain.
- Correctness and replayability do not require upstream calls.
- Keys and raw cell values are NEVER logged.
- Stdout JSON sink runs always; Local JSONL and Gateway stubs are pluggable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Sequence

ZERO_HASH = "0000000000000000000000000000000000000000000000000000000000000000"


def compute_event_hash(
    seq: int,
    prev_hash: str,
    event_type: str,
    timestamp: str,
    data: dict[str, Any],
) -> str:
    """Calculate deterministic SHA-256 hash for an event."""
    canonical_data = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    payload = f"{seq}:{prev_hash}:{event_type}:{timestamp}:{canonical_data}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def verify_hash_chain(events: Sequence[dict[str, Any]]) -> tuple[bool, str]:
    """Verify cryptographic integrity of an event sequence.

    Returns:
        (is_valid, diagnostic_message)
    """
    if not events:
        return True, "Empty event log; valid."

    for i, event in enumerate(events):
        seq = event.get("seq")
        prev_hash = event.get("prev_hash")
        event_hash = event.get("hash")
        event_type = event.get("event_type")
        timestamp = event.get("timestamp")
        data = event.get("data")

        if seq != i:
            return False, f"Sequence error at index {i}: expected seq={i}, got seq={seq}."

        if i == 0:
            if prev_hash != ZERO_HASH:
                return (
                    False,
                    f"Root event prev_hash invalid at seq 0: expected {ZERO_HASH}, got {prev_hash}.",
                )
        else:
            expected_prev = events[i - 1].get("hash")
            if prev_hash != expected_prev:
                return (
                    False,
                    f"Hash link broken at seq {i}: expected prev_hash {expected_prev}, got {prev_hash}.",
                )

        if not event_type or not timestamp or data is None:
            return False, f"Malformed event structure at seq {i}."

        expected_hash = compute_event_hash(
            seq=seq,
            prev_hash=prev_hash,
            event_type=event_type,
            timestamp=timestamp,
            data=data,
        )
        if event_hash != expected_hash:
            return (
                False,
                f"Tampered or corrupted hash at seq {i}: expected {expected_hash}, got {event_hash}.",
            )

    root_short = events[0]["hash"][:8]
    head_short = events[-1]["hash"][:8]
    return True, f"Hash chain verified: {len(events)} events (root {root_short}... -> head {head_short}...)."


class LogSink(ABC):
    """Abstract interface for event destinations."""

    @abstractmethod
    def emit(self, session_id: str, event: dict[str, Any]) -> None:
        """Emit an immutable log event."""

    def flush(self) -> None:
        """Flush any buffered events."""


class StdoutJsonLogSink(LogSink):
    """Outputs structured JSON events directly to stdout."""

    def __init__(self, out_stream=sys.stdout) -> None:
        self.out_stream = out_stream

    def emit(self, session_id: str, event: dict[str, Any]) -> None:
        record = {
            "session_id": session_id,
            "seq": event.get("seq"),
            "prev_hash": event.get("prev_hash"),
            "hash": event.get("hash"),
            "event_type": event.get("event_type"),
            "timestamp": event.get("timestamp"),
            "data": event.get("data"),
        }
        try:
            line = json.dumps(record, separators=(",", ":"), ensure_ascii=False)
            self.out_stream.write(line + "\n")
            self.out_stream.flush()
        except Exception:
            pass


class LocalJsonlLogSink(LogSink):
    """Appends event records to a local JSONL file."""

    def __init__(self, file_path: Path | str) -> None:
        self.file_path = Path(file_path).resolve()
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, session_id: str, event: dict[str, Any]) -> None:
        record = {
            "session_id": session_id,
            "seq": event.get("seq"),
            "prev_hash": event.get("prev_hash"),
            "hash": event.get("hash"),
            "event_type": event.get("event_type"),
            "timestamp": event.get("timestamp"),
            "data": event.get("data"),
        }
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


class GatewayLogSink(LogSink):
    """Sink for forwarding event batches to /internal/log on the Edge Gateway.

    Invariants:
    - Requests signed with HMAC-SHA256 per contract/auth.md.
    - Fails open: If the gateway is unreachable, logs warning and never halts execution.
    """

    def __init__(
        self,
        gateway_url: str | None = None,
        endpoint: str = "/internal/log",
        secret: str | None = None,
    ) -> None:
        self.gateway_url = gateway_url
        self.endpoint = endpoint
        self.secret = secret
        self.buffered_events: list[tuple[str, dict[str, Any]]] = []

    def emit(self, session_id: str, event: dict[str, Any]) -> None:
        self.buffered_events.append((session_id, event))
        self.flush()

    def flush(self) -> None:
        if not self.buffered_events:
            return

        settings = get_settings()
        base_url = self.gateway_url or getattr(settings, "GATEWAY_URL", None)
        secret = self.secret or getattr(settings, "GATEWAY_HMAC_SECRET_CURRENT", None)

        if not base_url or not secret:
            self.buffered_events.clear()
            return

        import urllib.request
        from tabchat.middleware.auth import sign_gateway_request

        batches: dict[str, list[dict[str, Any]]] = {}
        for s_id, ev in self.buffered_events:
            batches.setdefault(s_id, []).append(ev)
        self.buffered_events.clear()

        for s_id, evs in batches.items():
            payload = {"session_id": s_id, "events": evs}
            raw_body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            path = self.endpoint
            hmac_headers = sign_gateway_request(secret, "POST", path, raw_body)

            target_url = f"{base_url.rstrip('/')}{path}"
            req = urllib.request.Request(
                target_url,
                data=raw_body,
                headers={
                    "Content-Type": "application/json",
                    **hmac_headers,
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=5.0):
                    pass
            except Exception as e:
                # Fails open: log warning, never block pipeline execution
                sys.stderr.write(f"Warning: Gateway log sink unreachable, failing open: {e}\n")


class GatewayLogSinkStub(GatewayLogSink):
    """Backward-compatible alias for GatewayLogSink."""


class CompositeLogSink(LogSink):
    """Multiplexes events to multiple destinations."""

    def __init__(self, sinks: list[LogSink]) -> None:
        self.sinks = list(sinks)

    def emit(self, session_id: str, event: dict[str, Any]) -> None:
        for sink in self.sinks:
            try:
                sink.emit(session_id, event)
            except Exception:
                pass

    def flush(self) -> None:
        for sink in self.sinks:
            try:
                sink.flush()
            except Exception:
                pass


class EventChainLogger:
    """Manages sequential hash chaining and sink emission per session."""

    def __init__(self, sink: LogSink | None = None) -> None:
        self.sink = sink or StdoutJsonLogSink()
        self._session_events: dict[str, list[dict[str, Any]]] = {}

    def log_event(
        self,
        session_id: str,
        event_type: str,
        data: dict[str, Any],
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        """Create, hash, chain, and emit a new event."""
        if session_id not in self._session_events:
            self._session_events[session_id] = []

        events = self._session_events[session_id]
        seq = len(events)
        prev_hash = events[-1]["hash"] if seq > 0 else ZERO_HASH
        ts = timestamp or datetime.now(timezone.utc).isoformat()

        event_hash = compute_event_hash(
            seq=seq,
            prev_hash=prev_hash,
            event_type=event_type,
            timestamp=ts,
            data=data,
        )

        event = {
            "seq": seq,
            "prev_hash": prev_hash,
            "hash": event_hash,
            "event_type": event_type,
            "timestamp": ts,
            "data": data,
        }

        events.append(event)
        self.sink.emit(session_id, event)
        return event

    def get_events(self, session_id: str) -> list[dict[str, Any]]:
        """Retrieve recorded events for a session."""
        return list(self._session_events.get(session_id, []))


# Global default logger
_DEFAULT_LOGGER: EventChainLogger | None = None


def get_event_logger() -> EventChainLogger:
    """Retrieve singleton EventChainLogger."""
    global _DEFAULT_LOGGER
    if _DEFAULT_LOGGER is None:
        _DEFAULT_LOGGER = EventChainLogger()
    return _DEFAULT_LOGGER
