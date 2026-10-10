"""Gateway-to-Backend HMAC Authentication Middleware.

Specification: contract/auth.md
Invariants:
- Backend accepts only HMAC-signed gateway requests, except GET /health.
- 30-second timestamp skew tolerance.
- Dual-secret rotation (current and previous).
- Rejection returns HTTP 401 with standard error envelope.
- GET /health stays open and reveals nothing sensitive.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Callable, Optional
import uuid

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from tabchat.config import get_settings

SKEW_TOLERANCE_SECONDS = 30
EMPTY_BODY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def compute_body_sha256(raw_bytes: bytes) -> str:
    """Calculate hex SHA-256 digest of body bytes."""
    if not raw_bytes:
        return EMPTY_BODY_SHA256
    return hashlib.sha256(raw_bytes).hexdigest()


def build_canonical_string(
    timestamp: int,
    method: str,
    path: str,
    body_sha256: str,
    request_id: str,
) -> bytes:
    """Construct canonical byte string per contract/auth.md Section 3."""
    return f"{timestamp}\n{method.upper()}\n{path}\n{body_sha256}\n{request_id}".encode("utf-8")


def calculate_signature(secret: str, canonical_bytes: bytes) -> str:
    """Calculate HMAC-SHA256 hex signature."""
    return hmac.new(secret.encode("utf-8"), canonical_bytes, hashlib.sha256).hexdigest()


def sign_gateway_request(
    secret: str,
    method: str,
    path: str,
    raw_body_bytes: bytes = b"",
    request_id: str | None = None,
    timestamp: int | None = None,
) -> dict[str, str]:
    """Helper to generate required gateway headers for a request."""
    ts = timestamp if timestamp is not None else int(time.time())
    req_id = request_id or f"req_{uuid.uuid4().hex[:12]}"
    body_hash = compute_body_sha256(raw_body_bytes)
    canonical = build_canonical_string(ts, method, path, body_hash, req_id)
    sig = calculate_signature(secret, canonical)
    return {
        "X-Gateway-Timestamp": str(ts),
        "X-Gateway-Request-ID": req_id,
        "X-Gateway-Signature": sig,
    }


def verify_gateway_request(
    headers: dict[str, str],
    method: str,
    path: str,
    raw_body_bytes: bytes,
    current_secret: str,
    previous_secret: str | None = None,
    now_override: int | None = None,
) -> bool:
    """Verify incoming request against current and optional previous HMAC secrets."""
    ts_str = headers.get("X-Gateway-Timestamp") or headers.get("x-gateway-timestamp")
    req_id = headers.get("X-Gateway-Request-ID") or headers.get("x-gateway-request-id")
    signature = headers.get("X-Gateway-Signature") or headers.get("x-gateway-signature")

    if not ts_str or not req_id or not signature:
        return False

    try:
        ts = int(ts_str)
    except ValueError:
        return False

    # 1. Skew tolerance check
    now = now_override if now_override is not None else int(time.time())
    if abs(now - ts) > SKEW_TOLERANCE_SECONDS:
        return False

    # 2. Body SHA-256
    body_hash = compute_body_sha256(raw_body_bytes)

    # 3. Canonical string
    canonical = build_canonical_string(ts, method, path, body_hash, req_id)

    # 4. Constant-time signature comparison with current secret
    expected_current = calculate_signature(current_secret, canonical)
    if hmac.compare_digest(signature, expected_current):
        return True

    # 5. Dual-secret evaluation with previous secret
    if previous_secret:
        expected_prev = calculate_signature(previous_secret, canonical)
        if hmac.compare_digest(signature, expected_prev):
            return True

    return False


class GatewayHMACMiddleware(BaseHTTPMiddleware):
    """FastAPI/Starlette middleware enforcing HMAC authentication."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # GET /health is explicitly exempt from HMAC verification per contract/auth.md
        if request.url.path == "/health" and request.method == "GET":
            return await call_next(request)

        settings = get_settings()
        current_secret = getattr(request.app.state, "gateway_hmac_secret_current", None) or settings.GATEWAY_HMAC_SECRET_CURRENT
        previous_secret = getattr(request.app.state, "gateway_hmac_secret_previous", None) or settings.GATEWAY_HMAC_SECRET_PREVIOUS

        # If HMAC secret is not configured (e.g. offline dev without secrets), allow bypass
        if not current_secret:
            return await call_next(request)

        # Buffer raw body bytes so downstream handlers can re-read it
        raw_body_bytes = await request.body()

        # Extract path with query string if present
        path = request.url.path
        if request.url.query:
            path = f"{path}?{request.url.query}"

        headers = dict(request.headers)
        is_valid = verify_gateway_request(
            headers=headers,
            method=request.method,
            path=path,
            raw_body_bytes=raw_body_bytes,
            current_secret=current_secret,
            previous_secret=previous_secret,
        )

        if not is_valid:
            req_id = headers.get("x-gateway-request-id") or headers.get("X-Gateway-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "validation",
                        "message": "Gateway HMAC signature verification failed or timestamp skew exceeded.",
                        "request_id": req_id,
                    }
                },
            )

        return await call_next(request)
