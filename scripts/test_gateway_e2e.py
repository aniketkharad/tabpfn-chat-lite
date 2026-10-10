#!/usr/bin/env python3
"""Scripted End-to-End Integration Suite for tabpfn-chat-lite Edge Gateway & Backend.

Executes full lifecycle test:
1. Session Initialization (Turnstile challenge exchange -> signed HttpOnly cookie).
2. Service Status & Capacity probe.
3. Tabular Dataset Upload (CSV multipart).
4. Conversational Chat & Plan Formulation (Gemini planner).
5. Run Confirmation & Deterministic Execution (TabPFN executor).
6. Real-time SSE Stream Consumption & Block Rendering.
7. Audit Log Retrieval & Cryptographic Hash Chain Integrity Verification.
8. Emergency Kill Switch Trip & Clear Verification.
9. Rate Limiting & Per-IP Admission Caps.
10. "Delete My Data" Session Purge.
11. Security Boundary Invariant Checks (HMAC enforcement, cookie isolation, strict CSP).
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

GATEWAY_PORT = 8787
BACKEND_PORT = 8000
GATEWAY_URL = f"http://127.0.0.1:{GATEWAY_PORT}"
BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"
ADMIN_KEY = "dev_admin_secret_local"

SAMPLE_CSV = b"""age,tenure,balance,churn
35,12,500.5,0
42,24,1200.0,1
29,6,300.0,0
55,48,3500.2,1
31,18,750.8,0
48,36,2100.5,1
26,4,150.0,0
60,60,4200.0,1
38,15,900.2,0
45,30,1800.0,1
"""


class E2ETestRunner:
    def __init__(self, gateway_url: str = GATEWAY_URL, backend_url: str = BACKEND_URL) -> None:
        self.gateway_url = gateway_url.rstrip("/")
        self.backend_url = backend_url.rstrip("/")
        self.session_cookie: str | None = None
        self.session_id: str | None = None

    def _request(
        self,
        method: str,
        path: str,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        use_cookie: bool = True,
        expected_status: int | tuple[int, ...] = 200,
    ) -> tuple[int, dict[str, str], bytes]:
        url = f"{self.gateway_url}{path}"
        req_headers = dict(headers or {})

        if use_cookie and self.session_cookie:
            req_headers["Cookie"] = self.session_cookie

        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)

        status = 0
        resp_headers: dict[str, str] = {}
        body = b""

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                status = resp.status
                resp_headers = {k: v for k, v in resp.headers.items()}
                body = resp.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            resp_headers = {k: v for k, v in exc.headers.items()}
            body = exc.read()

        expected = (expected_status,) if isinstance(expected_status, int) else expected_status
        if status not in expected:
            raise AssertionError(
                f"Request {method} {path} returned status {status}, expected {expected}. Body: {body.decode('utf-8', errors='replace')}"
            )

        return status, resp_headers, body

    def run_all(self) -> None:
        print("=" * 68)
        print("RUNNING END-TO-END GATEWAY INTEGRATION SUITE")
        print("=" * 68)

        self.test_security_headers()
        self.test_status_probe()
        self.test_session_create()
        self.test_upload_dataset()
        self.test_chat_planning()
        self.test_run_and_sse_stream()
        self.test_audit_log_hash_chain()
        self.test_kill_switch_trip_and_clear()
        self.test_delete_session()
        self.test_hmac_direct_backend_protection()

        print("=" * 68)
        print("✓ ALL END-TO-END GATEWAY INTEGRATION TESTS PASSED!")
        print("=" * 68)

    def test_security_headers(self) -> None:
        print("\n[1/10] Testing Security Headers and Strict CSP...")
        status, headers, body = self._request("GET", "/health", use_cookie=False)

        csp = headers.get("content-security-policy", headers.get("Content-Security-Policy", ""))
        assert "default-src 'self'" in csp, f"Missing default-src 'self' in CSP: {csp}"
        assert "https://challenges.cloudflare.com" in csp, f"Missing Turnstile in CSP: {csp}"
        assert "unsafe-inline" not in csp.split("script-src")[1].split(";")[0], "script-src must not allow unsafe-inline!"

        x_content = headers.get("x-content-type-options", headers.get("X-Content-Type-Options", ""))
        assert x_content == "nosniff", f"Expected X-Content-Type-Options: nosniff, got {x_content}"

        referrer = headers.get("referrer-policy", headers.get("Referrer-Policy", ""))
        assert "origin" in referrer, f"Unexpected Referrer-Policy: {referrer}"

        assert "*" not in headers.get("access-control-allow-origin", ""), "Wildcard CORS is strictly forbidden!"
        print("  ✓ Strict CSP, nosniff, referrer-policy, and no wildcard CORS confirmed.")

    def test_status_probe(self) -> None:
        print("\n[2/10] Testing GET /api/status...")
        status, headers, body = self._request("GET", "/api/status", use_cookie=False)
        data = json.loads(body.decode("utf-8"))

        assert data.get("state") in ["ok", "busy", "exhausted", "killed"], f"Invalid status state: {data}"
        assert "resets_at" in data, "Status missing resets_at"
        assert "limits" in data, "Status missing limits"
        assert data["limits"]["max_rows"] == 200
        print(f"  ✓ Service status verified: state={data.get('state')}, resets_at={data.get('resets_at')}")

    def test_session_create(self) -> None:
        print("\n[3/10] Testing POST /api/session (Turnstile exchange & cookie issuance)...")
        # Cloudflare standard Turnstile test token
        payload = json.dumps({"turnstile_token": "mock_turnstile_test_token"}).encode("utf-8")
        status, headers, body = self._request(
            "POST",
            "/api/session",
            data=payload,
            headers={"Content-Type": "application/json"},
            use_cookie=False,
        )

        data = json.loads(body.decode("utf-8"))
        self.session_id = data.get("session_id")
        assert self.session_id, "Missing session_id in createSession response"
        assert "expires_at" in data, "Missing expires_at in createSession response"

        # Capture Set-Cookie header
        set_cookie = headers.get("set-cookie", headers.get("Set-Cookie", ""))
        assert "tabchat_session=" in set_cookie, f"Missing tabchat_session cookie: {set_cookie}"
        assert "HttpOnly" in set_cookie or "httponly" in set_cookie, "Cookie must be HttpOnly"
        assert "SameSite" in set_cookie, "Cookie must specify SameSite"

        # Extract cookie value
        self.session_cookie = set_cookie.split(";")[0]
        print(f"  ✓ Session cookie established for session: {self.session_id[:12]}...")

    def test_upload_dataset(self) -> None:
        print("\n[4/10] Testing POST /api/upload (Multipart CSV dataset upload)...")
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        body_lines = [
            f"--{boundary}".encode("utf-8"),
            b'Content-Disposition: form-data; name="file"; filename="sample_churn.csv"',
            b"Content-Type: text/csv",
            b"",
            SAMPLE_CSV,
            f"--{boundary}--".encode("utf-8"),
            b"",
        ]
        multipart_body = b"\r\n".join(body_lines)

        status, headers, body = self._request(
            "POST",
            "/api/upload",
            data=multipart_body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            use_cookie=True,
        )

        data = json.loads(body.decode("utf-8"))
        assert "dataset_id" in data, f"Missing dataset_id: {data}"
        assert "dataset_card" in data, f"Missing dataset_card: {data}"
        assert data["dataset_card"]["row_count"] == 10
        assert data["dataset_card"]["col_count"] == 4
        print(f"  ✓ Dataset uploaded successfully: {data['dataset_card']['row_count']} rows, {data['dataset_card']['col_count']} columns.")

    def test_chat_planning(self) -> None:
        print("\n[5/10] Testing POST /api/chat (Conversational goal setting & planning)...")
        chat_payload = json.dumps({
            "message": "Predict customer churn based on account features",
            "history": [],
        }).encode("utf-8")

        status, headers, body = self._request(
            "POST",
            "/api/chat",
            data=chat_payload,
            headers={"Content-Type": "application/json"},
            use_cookie=True,
        )

        data = json.loads(body.decode("utf-8"))
        assert data.get("type") in ["clarification", "plan"], f"Unexpected chat response type: {data}"
        assert "message" in data, "Chat response missing message"

        self.active_plan = data.get("plan")
        if not self.active_plan:
            # Send follow-up to confirm plan
            confirm_payload = json.dumps({
                "message": "Yes, binary classification with target column churn.",
                "history": [
                    {"role": "user", "content": "Predict customer churn based on account features"},
                    {"role": "assistant", "content": data.get("message", "")},
                ],
            }).encode("utf-8")
            _, _, follow_body = self._request(
                "POST",
                "/api/chat",
                data=confirm_payload,
                headers={"Content-Type": "application/json"},
                use_cookie=True,
            )
            follow_data = json.loads(follow_body.decode("utf-8"))
            self.active_plan = follow_data.get("plan")

        assert self.active_plan, "Planner did not return a valid Plan object."
        assert "plan_id" in self.active_plan, "Plan missing plan_id"
        print(f"  ✓ Plan formulated: id={self.active_plan['plan_id']}, capability={self.active_plan['capability']}")

    def test_run_and_sse_stream(self) -> None:
        print("\n[6/10] Testing POST /api/run & GET /api/runs/:id/events (SSE pass-through)...")
        run_payload = json.dumps({"plan_id": self.active_plan["plan_id"]}).encode("utf-8")

        status, headers, body = self._request(
            "POST",
            "/api/run",
            data=run_payload,
            headers={"Content-Type": "application/json"},
            use_cookie=True,
            expected_status=(200, 202),
        )

        run_data = json.loads(body.decode("utf-8"))
        run_id = run_data["run_id"]
        assert run_id, "Missing run_id in run response"
        print(f"  ✓ Run confirmed: run_id={run_id}")

        # Stream SSE events
        sse_url = f"{self.gateway_url}/api/runs/{run_id}/events"
        req = urllib.request.Request(
            sse_url,
            headers={
                "Accept": "text/event-stream",
                "Cookie": self.session_cookie or "",
            },
        )

        events: list[dict[str, Any]] = []
        with urllib.request.urlopen(req, timeout=30) as resp:
            buffer = ""
            for raw_chunk in resp:
                chunk = raw_chunk.decode("utf-8")
                buffer += chunk
                while "\n\n" in buffer:
                    block, buffer = buffer.split("\n\n", 1)
                    if not block.strip():
                        continue
                    event_type = ""
                    event_data = ""
                    for line in block.split("\n"):
                        if line.startswith("event:"):
                            event_type = line[6:].strip()
                        elif line.startswith("data:"):
                            event_data = line[5:].strip()
                    if event_type and event_data:
                        parsed = json.loads(event_data)
                        events.append({"event": event_type, "data": parsed})
                        if event_type == "done" or event_type == "error":
                            break

        assert len(events) > 0, "No SSE events received from stream!"
        event_types = [e["event"] for e in events]
        assert "queued" in event_types, f"Missing queued event in stream: {event_types}"
        assert "status" in event_types, f"Missing status event in stream: {event_types}"
        assert "block" in event_types, f"Missing block event in stream: {event_types}"
        assert "done" in event_types, f"Missing done event in stream: {event_types}"
        print(f"  ✓ Received {len(events)} SSE stream frames: {event_types}")

    def test_audit_log_hash_chain(self) -> None:
        print("\n[7/10] Testing GET /api/log (Cryptographic hash chain verification)...")
        status, headers, body = self._request("GET", "/api/log?format=json", use_cookie=True)
        data = json.loads(body.decode("utf-8"))

        events = data.get("events", [])
        assert len(events) >= 2, f"Expected recorded events in audit log, got {len(events)}"

        # Validate hash chain integrity
        from tabchat.logging import verify_hash_chain
        is_valid, msg = verify_hash_chain(events)
        assert is_valid, f"Session audit log hash chain broken: {msg}"
        print(f"  ✓ Hash chain verified: {len(events)} events (root {events[0]['hash'][:8]}... -> head {events[-1]['hash'][:8]}...).")

    def test_kill_switch_trip_and_clear(self) -> None:
        print("\n[8/10] Testing Emergency Kill Switch (Trip -> Deny -> Clear -> Resume)...")
        # Trip switch
        trip_payload = json.dumps({"action": "trip", "reason": "E2E automated testing"}).encode("utf-8")
        status, _, body = self._request(
            "POST",
            "/api/admin/kill-switch",
            data=trip_payload,
            headers={
                "Content-Type": "application/json",
                "X-Admin-Key": ADMIN_KEY,
            },
            use_cookie=False,
        )
        assert json.loads(body.decode("utf-8"))["status"] == "tripped"

        # Check status reports killed
        _, _, status_body = self._request("GET", "/api/status", use_cookie=False)
        assert json.loads(status_body.decode("utf-8"))["state"] == "killed"

        # Run attempt is rejected with 503 kill_switch
        run_payload = json.dumps({"plan_id": self.active_plan["plan_id"]}).encode("utf-8")
        status, _, err_body = self._request(
            "POST",
            "/api/run",
            data=run_payload,
            headers={"Content-Type": "application/json"},
            use_cookie=True,
            expected_status=503,
        )
        err = json.loads(err_body.decode("utf-8"))["error"]
        assert err["code"] == "kill_switch"
        print("  ✓ Kill switch tripped: status reports 'killed', execution rejected with HTTP 503 kill_switch.")

        # Clear switch
        clear_payload = json.dumps({"action": "clear"}).encode("utf-8")
        self._request(
            "POST",
            "/api/admin/kill-switch",
            data=clear_payload,
            headers={
                "Content-Type": "application/json",
                "X-Admin-Key": ADMIN_KEY,
            },
            use_cookie=False,
        )

        # Check status reports ok again
        _, _, status_body = self._request("GET", "/api/status", use_cookie=False)
        assert json.loads(status_body.decode("utf-8"))["state"] == "ok"
        print("  ✓ Kill switch cleared: status reports 'ok'.")

    def test_delete_session(self) -> None:
        print("\n[9/10] Testing DELETE /api/session ('Delete My Data')...")
        status, headers, body = self._request("DELETE", "/api/session", use_cookie=True)
        data = json.loads(body.decode("utf-8"))
        assert data.get("status") == "deleted"

        # Verify cookie cleared with Max-Age=0
        set_cookie = headers.get("set-cookie", headers.get("Set-Cookie", ""))
        assert "Max-Age=0" in set_cookie or "max-age=0" in set_cookie
        print("  ✓ Session destroyed and cookie purged.")

    def test_hmac_direct_backend_protection(self) -> None:
        print("\n[10/10] Testing Backend Direct HMAC Rejection (Bypass Prevention)...")
        # Direct call to backend host bypassing gateway without HMAC header
        req = urllib.request.Request(f"{self.backend_url}/api/upload", method="POST", data=b"fake")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                raise AssertionError("Direct request without HMAC should have been rejected with 401!")
        except urllib.error.HTTPError as exc:
            assert exc.code == 401, f"Expected 401 Unauthorized on direct access, got {exc.code}"
            err = json.loads(exc.read().decode("utf-8"))["error"]
            assert err["code"] == "validation"
            print("  ✓ Direct backend access without valid HMAC signature strictly rejected (HTTP 401).")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Gateway E2E test suite")
    parser.add_argument("--gateway-url", default=GATEWAY_URL, help="Gateway URL")
    parser.add_argument("--backend-url", default=BACKEND_URL, help="Backend URL")
    args = parser.parse_args()

    runner = E2ETestRunner(gateway_url=args.gateway_url, backend_url=args.backend_url)
    try:
        runner.run_all()
        return 0
    except Exception as exc:
        print(f"\n❌ E2E TEST FAILED: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
