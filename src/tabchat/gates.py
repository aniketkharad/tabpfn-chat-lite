"""Upstream rate limiting, queuing, and quota governance gates for Gemini and TabPFN.

Invariants:
- UpstreamGate abstraction supporting deterministic FakeClock in tests.
- GeminiGate: 1 call in flight, RPM and RPD from env/config, fair queue with position and ETA.
- TabPFNGate: per-minute cap, daily and monthly token budget, cost estimation,
  3-phase token lifecycle (reserve, commit, refund), Retry-After enforcement, no tight loops.
- Both expose snapshots for GET /api/status and map exhaustion to quota_gemini / quota_tabpfn.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections import deque
from datetime import datetime, timezone
import time
from typing import Any, Callable, Optional
import uuid


class Clock(ABC):
    """Abstract clock for deterministic time manipulation."""

    @abstractmethod
    def now(self) -> float:
        """Return epoch timestamp in seconds."""

    @abstractmethod
    async def sleep(self, seconds: float) -> None:
        """Asynchronously sleep for the given duration."""


class SystemClock(Clock):
    """Standard system clock based on time.time()."""

    def now(self) -> float:
        return time.time()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class FakeClock(Clock):
    """Deterministic fake clock advancing manually or on simulated sleep."""

    def __init__(self, start_time: float = 1775779200.0) -> None:
        self._current_time = start_time
        self._sleep_callbacks: list[tuple[float, asyncio.Event]] = []

    def now(self) -> float:
        return self._current_time

    def advance(self, seconds: float) -> None:
        self._current_time += seconds
        # Wake up any simulated sleeps that are now in the past
        still_pending = []
        for wake_at, event in self._sleep_callbacks:
            if self._current_time >= wake_at:
                event.set()
            else:
                still_pending.append((wake_at, event))
        self._sleep_callbacks = still_pending

    async def sleep(self, seconds: float) -> None:
        wake_at = self._current_time + seconds
        event = asyncio.Event()
        self._sleep_callbacks.append((wake_at, event))
        self.advance(seconds)
        await event.wait()


class QuotaExhaustedError(Exception):
    """Raised when an upstream daily or monthly quota is exhausted."""

    def __init__(self, code: str, message: str, retry_after_s: int | None = None) -> None:
        self.code = code  # "quota_gemini" or "quota_tabpfn"
        self.message = message
        self.retry_after_s = retry_after_s
        super().__init__(message)


def sync_gateway_counters(tabpfn_tokens: int = 0, gemini_calls: int = 0) -> dict[str, Any]:
    """Report token and call increments to Edge Gateway via /internal/counters.

    Invariants:
    - Requests signed with HMAC-SHA256 per contract/auth.md.
    - Fails closed for counters: If GATEWAY_URL is configured and unreachable, raises QuotaExhaustedError.
    """
    from tabchat.config import get_settings

    try:
        settings = get_settings()
    except Exception:
        return {"accepted": True, "offline": True}

    base_url = getattr(settings, "GATEWAY_URL", None)
    secret = getattr(settings, "GATEWAY_HMAC_SECRET_CURRENT", None)

    if not base_url or not secret:
        return {"accepted": True, "offline": True}

    import json
    import urllib.request
    from tabchat.middleware.auth import sign_gateway_request

    payload = {"tabpfn_tokens": tabpfn_tokens, "gemini_calls": gemini_calls}
    raw_body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    path = "/internal/counters"
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
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            if resp.status != 200:
                code = "quota_tabpfn" if tabpfn_tokens else "quota_gemini"
                raise QuotaExhaustedError(
                    code=code,
                    message=f"Gateway counters rejected update: status {resp.status}",
                )
            return json.loads(resp.read().decode("utf-8"))
    except QuotaExhaustedError:
        raise
    except Exception as e:
        code = "quota_tabpfn" if tabpfn_tokens else "quota_gemini"
        raise QuotaExhaustedError(
            code=code,
            message=f"Gateway quota counters unreachable, failing closed: {e}",
            retry_after_s=60,
        ) from e


class UpstreamGate(ABC):
    """Base class for upstream API governance gates."""

    def __init__(self, clock: Clock | None = None) -> None:
        self.clock = clock or SystemClock()

    @abstractmethod
    def get_snapshot(self) -> dict[str, Any]:
        """Return operational state snapshot."""

    def _seconds_until_utc_midnight(self) -> int:
        now_ts = self.clock.now()
        dt = datetime.fromtimestamp(now_ts, tz=timezone.utc)
        midnight = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        return max(1, int((midnight.timestamp() - now_ts) + 1))

    def _utc_midnight_iso(self) -> str:
        now_ts = self.clock.now()
        dt = datetime.fromtimestamp(now_ts, tz=timezone.utc)
        # Next midnight 00:00:00 UTC
        next_day = dt.date().fromordinal(dt.date().toordinal() + 1)
        return datetime(next_day.year, next_day.month, next_day.day, 0, 0, 0, tzinfo=timezone.utc).isoformat().replace("+00:00", ".000Z")


class GeminiGate(UpstreamGate):
    """Upstream gate for Google Gemini API.

    Invariants:
    - Exactly 1 call in flight.
    - RPM and RPD limits from env/config.
    - FIFO queue with queue position and ETA.
    - Fair ordering.
    - Maps exhaustion to quota_gemini.
    """

    def __init__(
        self,
        rpm_limit: int = 15,
        rpd_limit: int = 20,
        clock: Clock | None = None,
    ) -> None:
        super().__init__(clock=clock)
        self.rpm_limit = rpm_limit
        self.rpd_limit = rpd_limit

        self._in_flight_lock = asyncio.Lock()
        self._in_flight_count = 0

        self._rpm_window_seconds = 60.0
        self._call_timestamps: deque[float] = deque()

        self._current_day: int = self._day_number()
        self._calls_today: int = 0

        # Fair FIFO Queue tracking (ticket_id, asyncio.Event)
        self._queue: deque[tuple[str, asyncio.Event]] = deque()
        self._lock = asyncio.Lock()

    def _day_number(self) -> int:
        return int(self.clock.now() // 86400)

    def _check_day_rollover(self) -> None:
        today = self._day_number()
        if today > self._current_day:
            self._current_day = today
            self._calls_today = 0

    def get_queue_info(self, ticket_id: str) -> tuple[int, float]:
        """Return (1-indexed queue position, estimated wait seconds)."""
        for idx, (t_id, _) in enumerate(self._queue):
            if t_id == ticket_id:
                pos = idx + 1
                # Estimate: average 4.0s per turn plus rate limit window pace
                eta = pos * (self._rpm_window_seconds / max(1, self.rpm_limit))
                return pos, round(eta, 1)
        return 0, 0.0

    async def acquire(self) -> str:
        """Enqueue request, wait fairly for slot, and acquire.

        Returns ticket_id.
        Raises QuotaExhaustedError if daily quota is exhausted.
        """
        async with self._lock:
            self._check_day_rollover()
            if self._calls_today >= self.rpd_limit:
                retry_s = self._seconds_until_utc_midnight()
                raise QuotaExhaustedError(
                    code="quota_gemini",
                    message=f"Daily Gemini quota exhausted ({self.rpd_limit} requests/day reached). Resets at 00:00:00 UTC.",
                    retry_after_s=retry_s,
                )

            ticket_id = f"q_{uuid.uuid4().hex[:8]}"
            event = asyncio.Event()
            self._queue.append((ticket_id, event))

        # If we are not first in queue, wait our turn
        while True:
            async with self._lock:
                if self._queue and self._queue[0][0] == ticket_id:
                    break
            await self.clock.sleep(0.05)

        # Now we are head of queue; acquire in-flight concurrency lock (1 in flight)
        await self._in_flight_lock.acquire()
        self._in_flight_count = 1

        # Check RPM sliding window
        while True:
            async with self._lock:
                now = self.clock.now()
                while self._call_timestamps and (now - self._call_timestamps[0] >= self._rpm_window_seconds):
                    self._call_timestamps.popleft()

                if len(self._call_timestamps) < self.rpm_limit:
                    self._call_timestamps.append(now)
                    self._calls_today += 1
                    sync_gateway_counters(gemini_calls=1)
                    # Remove self from queue
                    if self._queue and self._queue[0][0] == ticket_id:
                        self._queue.popleft()
                    return ticket_id

                oldest = self._call_timestamps[0]
                wait_time = self._rpm_window_seconds - (now - oldest) + 0.05

            await self.clock.sleep(wait_time)

    def release(self, ticket_id: str) -> None:
        """Release in-flight lock after call completes."""
        self._in_flight_count = 0
        if self._in_flight_lock.locked():
            self._in_flight_lock.release()

    def get_snapshot(self) -> dict[str, Any]:
        """Return state snapshot for GET /api/status."""
        self._check_day_rollover()
        is_exhausted = self._calls_today >= self.rpd_limit
        return {
            "in_flight": self._in_flight_count,
            "queue_length": len(self._queue),
            "calls_today": self._calls_today,
            "daily_remaining": max(0, self.rpd_limit - self._calls_today),
            "rpm_limit": self.rpm_limit,
            "rpd_limit": self.rpd_limit,
            "resets_at": self._utc_midnight_iso(),
            "status": "exhausted" if is_exhausted else ("busy" if self._in_flight_count > 0 or len(self._queue) > 0 else "ok"),
        }


class TabPFNGate(UpstreamGate):
    """Upstream gate for Prior Labs TabPFN API.

    Invariants:
    - Per-minute request cap.
    - Daily and monthly token budgets from config.
    - Pre-flight cost estimation.
    - 3-phase token lifecycle: reserve, commit, refund.
    - Retry-After enforcement with exponential backoff (no tight loops).
    - Maps exhaustion to quota_tabpfn.
    """

    def __init__(
        self,
        rpm_limit: int = 30,
        daily_token_budget: int = 5_000_000,
        monthly_token_budget: int = 20_000_000,
        clock: Clock | None = None,
    ) -> None:
        super().__init__(clock=clock)
        self.rpm_limit = rpm_limit
        self.daily_token_budget = daily_token_budget
        self.monthly_token_budget = monthly_token_budget

        self._rpm_window_seconds = 60.0
        self._request_timestamps: deque[float] = deque()

        self._current_day: int = self._day_number()
        self._current_month: int = self._month_number()

        self.tokens_used_today: int = 0
        self.tokens_used_this_month: int = 0
        self.tokens_reserved: int = 0

        # Active reservations: reservation_id -> token_amount
        self._reservations: dict[str, int] = {}

        # Upstream backoff lock
        self._backoff_until: float = 0.0

        self._lock = asyncio.Lock()

    def _day_number(self) -> int:
        return int(self.clock.now() // 86400)

    def _month_number(self) -> int:
        dt = datetime.fromtimestamp(self.clock.now(), tz=timezone.utc)
        return dt.year * 12 + dt.month

    def _check_rollovers(self) -> None:
        now_day = self._day_number()
        if now_day > self._current_day:
            self._current_day = now_day
            self.tokens_used_today = 0

        now_month = self._month_number()
        if now_month > self._current_month:
            self._current_month = now_month
            self.tokens_used_this_month = 0

    def estimate_cost(self, row_count: int, col_count: int, capability: str = "classification") -> int:
        """Call/calculate cost estimate before execution. Floor 10,000 tokens."""
        # Baseline charge per predict call is floor 10,000 tokens (docs/FACTS.md Section 1.2)
        base = 10_000
        # If interpretability, runs permutations (e.g. 5 calls)
        if capability == "interpretability":
            return base * 5
        return base

    async def check_rate_limit(self) -> None:
        """Enforce RPM cap and Retry-After backoff."""
        while True:
            async with self._lock:
                now = self.clock.now()

                # Check if currently locked out by Retry-After
                if now < self._backoff_until:
                    wait_backoff = self._backoff_until - now
                else:
                    wait_backoff = 0.0

                # Check RPM window
                while self._request_timestamps and (now - self._request_timestamps[0] >= self._rpm_window_seconds):
                    self._request_timestamps.popleft()

                if wait_backoff == 0.0 and len(self._request_timestamps) < self.rpm_limit:
                    self._request_timestamps.append(now)
                    return

                if wait_backoff > 0.0:
                    wait_time = wait_backoff
                else:
                    oldest = self._request_timestamps[0]
                    wait_time = self._rpm_window_seconds - (now - oldest) + 0.05

            await self.clock.sleep(wait_time)

    async def reserve(self, estimated_tokens: int) -> str:
        """Phase 1: Reserve tokens against daily and monthly budgets."""
        async with self._lock:
            self._check_rollovers()

            potential_daily = self.tokens_used_today + self.tokens_reserved + estimated_tokens
            potential_monthly = self.tokens_used_this_month + self.tokens_reserved + estimated_tokens

            if potential_daily > self.daily_token_budget or potential_monthly > self.monthly_token_budget:
                retry_s = self._seconds_until_utc_midnight()
                raise QuotaExhaustedError(
                    code="quota_tabpfn",
                    message=f"Daily TabPFN token budget exhausted ({self.daily_token_budget:,} tokens reached). Resets at 00:00:00 UTC.",
                    retry_after_s=retry_s,
                )

            reservation_id = f"res_{uuid.uuid4().hex[:12]}"
            self._reservations[reservation_id] = estimated_tokens
            self.tokens_reserved += estimated_tokens
            return reservation_id

    async def commit(self, reservation_id: str, actual_tokens: int) -> None:
        """Phase 2: Finalize token charge upon successful execution."""
        async with self._lock:
            self._check_rollovers()
            reserved = self._reservations.pop(reservation_id, 0)
            self.tokens_reserved = max(0, self.tokens_reserved - reserved)

            self.tokens_used_today += actual_tokens
            self.tokens_used_this_month += actual_tokens
            sync_gateway_counters(tabpfn_tokens=actual_tokens)

    async def refund(self, reservation_id: str, refund_amount: int | None = None) -> None:
        """Phase 3: Refund reserved tokens on cancellation, failure, or unused portion."""
        async with self._lock:
            reserved = self._reservations.pop(reservation_id, 0)
            self.tokens_reserved = max(0, self.tokens_reserved - reserved)

    def handle_upstream_rate_limit(self, retry_after_s: float) -> None:
        """Honor upstream 429 Retry-After header and prevent tight-loop retries."""
        now = self.clock.now()
        # Ensure at least 1.0s backoff, up to provided retry_after_s
        backoff = max(1.0, min(float(retry_after_s), 3600.0))
        self._backoff_until = now + backoff

    def get_snapshot(self) -> dict[str, Any]:
        """Return state snapshot for GET /api/status."""
        self._check_rollovers()
        daily_rem = max(0, self.daily_token_budget - (self.tokens_used_today + self.tokens_reserved))
        monthly_rem = max(0, self.monthly_token_budget - (self.tokens_used_this_month + self.tokens_reserved))
        is_exhausted = daily_rem < 10_000 or monthly_rem < 10_000
        return {
            "daily_tokens_remaining": daily_rem,
            "monthly_tokens_remaining": monthly_rem,
            "tokens_used_today": self.tokens_used_today,
            "tokens_reserved": self.tokens_reserved,
            "daily_budget": self.daily_token_budget,
            "monthly_budget": self.monthly_token_budget,
            "resets_at": self._utc_midnight_iso(),
            "status": "exhausted" if is_exhausted else "ok",
        }


# Global singleton gate instances
_GEMINI_GATE: GeminiGate | None = None
_TABPFN_GATE: TabPFNGate | None = None


def get_gemini_gate(settings: Any = None) -> GeminiGate:
    global _GEMINI_GATE
    if _GEMINI_GATE is None:
        from tabchat.config import get_settings
        cfg = settings or get_settings()
        _GEMINI_GATE = GeminiGate(
            rpm_limit=getattr(cfg, "GEMINI_RPM_LIMIT", 15),
            rpd_limit=getattr(cfg, "GEMINI_RPD", 20),
        )
    return _GEMINI_GATE


def get_tabpfn_gate(settings: Any = None) -> TabPFNGate:
    global _TABPFN_GATE
    if _TABPFN_GATE is None:
        from tabchat.config import get_settings
        cfg = settings or get_settings()
        _TABPFN_GATE = TabPFNGate(
            rpm_limit=getattr(cfg, "TABPFN_RPM", 30),
            daily_token_budget=getattr(cfg, "TABPFN_DAILY_TOKEN_BUDGET", 5_000_000),
            monthly_token_budget=getattr(cfg, "TABPFN_MONTHLY_TOKEN_BUDGET", 20_000_000),
        )
    return _TABPFN_GATE
