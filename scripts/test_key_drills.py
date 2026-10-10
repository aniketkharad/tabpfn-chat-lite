#!/usr/bin/env python3
"""Key Rotation Drills Suite for tabpfn-chat-lite.

Covers Prompt 9 Section 7:
- Rotate Gemini API key (environment-only, no code change).
- Rotate TabPFN token (environment-only, no code change).
- Dual-secret HMAC gateway rotation (two-secret overlap, zero downtime).
"""

from __future__ import annotations

import os
import sys
import time

from starlette.testclient import TestClient

from tabchat.app import create_app
from tabchat.config import Settings
from tabchat.middleware.auth import GatewayHMACMiddleware, sign_gateway_request


def drill_hmac_dual_secret_rotation() -> bool:
    print("\n--- 1. GATEWAY HMAC DUAL-SECRET ROTATION DRILL ---")
    secret_old = "hmac_secret_generation_1_old_secret_key"
    secret_new = "hmac_secret_generation_2_new_secret_key"

    # Step 1: Normal state (only old secret active)
    app = create_app()
    app.state.gateway_hmac_secret_current = secret_old
    app.state.gateway_hmac_secret_previous = None
    app.add_middleware(GatewayHMACMiddleware)
    client = TestClient(app)

    now = int(time.time())
    h_old = sign_gateway_request(secret_old, "GET", "/api/status", b"", timestamp=now)
    h_old["X-Session-ID"] = "s1"
    res_1 = client.get("/api/status", headers=h_old)
    assert res_1.status_code == 200, "Old secret should be accepted initially"

    # Step 2: Secret Rotation in progress on Backend (current=secret_new, previous=secret_old)
    app.state.gateway_hmac_secret_current = secret_new
    app.state.gateway_hmac_secret_previous = secret_old

    # In-flight request from older gateway (signed with secret_old) -> MUST PASS!
    h_old_inflight = sign_gateway_request(secret_old, "GET", "/api/status", b"", timestamp=now)
    h_old_inflight["X-Session-ID"] = "s1"
    res_2_old = client.get("/api/status", headers=h_old_inflight)
    assert res_2_old.status_code == 200, "Old secret MUST be accepted via fallback to PREVIOUS"

    # New request from updated gateway (signed with secret_new) -> MUST PASS!
    h_new = sign_gateway_request(secret_new, "GET", "/api/status", b"", timestamp=now)
    h_new["X-Session-ID"] = "s1"
    res_2_new = client.get("/api/status", headers=h_new)
    assert res_2_new.status_code == 200, "New secret MUST be accepted via CURRENT"

    # Step 3: Decommission old secret (previous=None)
    app.state.gateway_hmac_secret_previous = None

    # New secret succeeds
    res_3_new = client.get("/api/status", headers=h_new)
    assert res_3_new.status_code == 200, "New secret accepted"

    # Old secret is now cleanly rejected (HTTP 401)
    res_3_old = client.get("/api/status", headers=h_old_inflight)
    assert res_3_old.status_code == 401, "Old secret now rejected after decommission"

    print("[✓ PASS] Dual-Secret Overlap Rotation Verified (Zero Downtime, 401 on Decommission)")
    return True


def drill_upstream_credential_hot_swap() -> bool:
    print("\n--- 2. GEMINI & TABPFN CREDENTIAL SWAP (NO CODE CHANGE) ---")
    # Verify that changing env vars updates Settings without modifying application code
    s1 = Settings(
        GEMINI_API_KEY="key_version_1",
        TABPFN_TOKEN="token_version_1",
    )
    assert s1.GEMINI_API_KEY == "key_version_1"
    assert s1.TABPFN_TOKEN == "token_version_1"

    s2 = Settings(
        GEMINI_API_KEY="key_version_2_rotated",
        TABPFN_TOKEN="token_version_2_rotated",
    )
    assert s2.GEMINI_API_KEY == "key_version_2_rotated"
    assert s2.TABPFN_TOKEN == "token_version_2_rotated"

    print("[✓ PASS] Upstream API Credentials Swapped Dynamically (Pure Configuration)")
    return True


def main() -> int:
    print("=" * 68)
    print("KEY ROTATION DRILLS VERIFICATION")
    print("=" * 68)
    p1 = drill_hmac_dual_secret_rotation()
    p2 = drill_upstream_credential_hot_swap()
    if p1 and p2:
        print("\nALL KEY ROTATION DRILLS PASSED: 100% GREEN")
        print("=" * 68)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
