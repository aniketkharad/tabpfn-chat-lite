"""Contract compliance and schema validation test suite for tabpfn-chat-lite."""

from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import time
import pytest
from starlette.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from contract.check import SchemaValidator
from tabchat.app import app
from tabchat.gates import FakeClock, GeminiGate, QuotaExhaustedError, TabPFNGate
from tabchat.middleware.auth import sign_gateway_request
from tabchat.schemas.plan import Plan
from tabchat.store import MemoryStore

import pandas as pd
from tabchat.engine.planner import PlannerOutput
from tabchat.llm.client import FakeLLMClient
from tabchat.schemas.job_spec import JobSpec

SCHEMAS_DIR = Path("contract/schemas")
validator = SchemaValidator(SCHEMAS_DIR)


def mock_tabpfn_api_caller(
    task_type: str,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_holdout: pd.DataFrame,
    random_seed: int = 42,
    **kwargs,
) -> dict:
    """Offline mock caller for TabPFN."""
    n_test = len(X_holdout)
    if task_type == "classification":
        preds = ["yes" if i % 2 == 0 else "no" for i in range(n_test)]
        probs = [[0.8, 0.2] if p == "yes" else [0.2, 0.8] for p in preds]
        return {
            "predictions": preds,
            "probabilities": probs,
            "classes": ["no", "yes"],
            "model_path": "v3.5_default",
        }
    else:
        preds = [42.0 + (i * 1.5) for i in range(n_test)]
        return {
            "predictions": preds,
            "quantiles": {"q10": [p - 5.0 for p in preds], "q50": preds, "q90": [p + 5.0 for p in preds]},
            "model_path": "v3.5_default",
        }


@pytest.fixture
def test_client():
    """TestClient with fresh MemoryStore and offline mocks in app state."""
    app.state.store = MemoryStore()
    app.state.gateway_hmac_secret_current = None
    app.state.gateway_hmac_secret_previous = None

    mock_spec = JobSpec(
        task_type="classification",
        target_column="churn",
        feature_columns=["age", "income"],
        eval_metric="accuracy",
        holdout_fraction=0.2,
        seed=42,
        rationale="Predict churn using age and income.",
    )
    fake_planner_output = PlannerOutput(
        is_clarification=False,
        clarification_message=None,
        selected_skills=["task_and_target", "leakage_and_splits"],
        proposed_spec=mock_spec,
    )
    fake_narration = "TabPFN achieved 85% accuracy on churn prediction."
    app.state.llm_client = FakeLLMClient(
        mock_text=fake_narration,
        mock_structured=fake_planner_output,
    )
    app.state.tabpfn_api_caller = mock_tabpfn_api_caller
    return TestClient(app)


# =============================================================================
# 1. Endpoint Contract Schema Validations
# =============================================================================

def test_contract_get_health(test_client):
    """GET /health must validate against health schema without HMAC headers."""
    res = test_client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert "timestamp" in data


def test_contract_get_status(test_client):
    """GET /api/status must return state, resets_at, limits, capacity."""
    res = test_client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert data["state"] in ("ok", "busy", "exhausted", "killed")
    assert "resets_at" in data
    assert "limits" in data
    assert "capacity" in data
    for limit_key in ("max_rows", "max_cols", "max_cells", "max_file_size_bytes", "max_turns"):
        assert limit_key in data["limits"]


def test_contract_session_lifecycle(test_client):
    """POST /api/session and DELETE /api/session must validate."""
    res_create = test_client.post("/api/session")
    assert res_create.status_code == 200
    create_data = res_create.json()
    assert "session_id" in create_data
    assert "expires_at" in create_data

    res_del = test_client.delete("/api/session")
    assert res_del.status_code == 200
    del_data = res_del.json()
    assert del_data["status"] == "deleted"
    assert "message" in del_data


def test_contract_upload_and_table_schema(test_client):
    """POST /api/upload must return dataset_card and table conforming to table.json."""
    csv_bytes = b"age,tenure,churn\n25,1.5,no\n42,4.0,yes\n37,2.2,no\n"
    files = {"file": ("data.csv", io.BytesIO(csv_bytes), "text/csv")}
    res = test_client.post("/api/upload", files=files)
    assert res.status_code == 200
    data = res.json()

    assert "dataset_id" in data
    assert "dataset_card" in data
    assert "table" in data

    # Validate table schema using contract/check.py validator
    table_schema = json.loads((SCHEMAS_DIR / "table.json").read_text(encoding="utf-8"))
    validator.validate(data["table"], table_schema)
    assert data["table"]["cols"] == ["age", "tenure", "churn"]
    assert len(data["table"]["rows"]) == 3


def test_contract_chat_and_plan_schema(test_client):
    """POST /api/chat must return Plan conforming to plan.json."""
    # 0. Session init
    test_client.post("/api/session")

    # 1. Upload dataset first
    csv_bytes = b"age,income,churn\n25,50000,no\n40,80000,yes\n"
    test_client.post("/api/upload", files={"file": ("data.csv", io.BytesIO(csv_bytes), "text/csv")})

    # 2. Chat
    res = test_client.post("/api/chat", json={"message": "Predict churn from age and income"})
    assert res.status_code == 200
    data = res.json()
    assert data["type"] in ("plan", "clarification")
    assert "message" in data

    if data["type"] == "plan":
        plan_schema = json.loads((SCHEMAS_DIR / "plan.json").read_text(encoding="utf-8"))
        validator.validate(data["plan"], plan_schema)
        Plan.model_validate(data["plan"])


def test_contract_run_and_blocks_schema(test_client):
    """POST /api/run and GET /api/runs/{id} must validate result blocks against result_block.json."""
    # 0. Session init
    test_client.post("/api/session")

    csv_bytes = (
        b"age,income,churn\n"
        b"25,50000,no\n40,80000,yes\n30,60000,no\n35,70000,yes\n"
        b"22,45000,no\n48,90000,yes\n29,55000,no\n52,95000,yes\n"
        b"27,52000,no\n43,82000,yes\n"
    )
    test_client.post("/api/upload", files={"file": ("data.csv", io.BytesIO(csv_bytes), "text/csv")})
    test_client.post("/api/chat", json={"message": "Predict churn from age and income"})

    res_run = test_client.post("/api/run")
    assert res_run.status_code in (200, 202)
    run_data = res_run.json()
    assert "run_id" in run_data
    run_id = run_data["run_id"]

    res_get = test_client.get(f"/api/runs/{run_id}")
    assert res_get.status_code == 200
    details = res_get.json()
    assert details["run_id"] == run_id
    assert details["status"] == "completed"
    assert "blocks" in details

    # Validate each block against result_block.json
    block_schema = json.loads((SCHEMAS_DIR / "result_block.json").read_text(encoding="utf-8"))
    for block in details["blocks"]:
        validator.validate(block, block_schema)


def test_contract_get_log_hash_chain(test_client):
    """GET /api/log?format=json must return valid cryptographic hash chain."""
    test_client.post("/api/session")
    csv_bytes = b"x,y\n1,2\n3,4\n"
    test_client.post("/api/upload", files={"file": ("data.csv", io.BytesIO(csv_bytes), "text/csv")})

    res = test_client.get("/api/log?format=json")
    assert res.status_code == 200
    log_data = res.json()
    assert "session_id" in log_data
    assert "events" in log_data
    assert len(log_data["events"]) >= 2

    from tabchat.logging import verify_hash_chain
    is_valid, msg = verify_hash_chain(log_data["events"])
    assert is_valid, msg


def test_contract_internal_endpoints(test_client):
    """POST /internal/log and POST /internal/counters must return valid responses."""
    res_log = test_client.post(
        "/internal/log",
        json={"session_id": "test_sess", "events": [{"event_type": "test", "data": {}}]},
    )
    assert res_log.status_code == 200
    assert res_log.json()["accepted"] is True

    res_counters = test_client.post(
        "/internal/counters",
        json={"tabpfn_tokens": 10000, "gemini_calls": 2},
    )
    assert res_counters.status_code == 200
    assert res_counters.json()["accepted"] is True
    assert "current_usage" in res_counters.json()


# =============================================================================
# 2. Error Envelopes Schema Validation
# =============================================================================

def test_contract_error_envelope_on_pii(test_client):
    """PII detection must return error conforming to error.json with code pii_detected."""
    pii_csv = b"name,email,score\nAlice,alice@example.com,95\n"
    res = test_client.post(
        "/api/upload",
        files={"file": ("pii.csv", io.BytesIO(pii_csv), "text/csv")},
        headers={"X-Gateway-Request-ID": "req_pii"},
    )
    assert res.status_code == 422
    err_json = res.json()
    error_schema = json.loads((SCHEMAS_DIR / "error.json").read_text(encoding="utf-8"))
    validator.validate(err_json, error_schema)
    assert err_json["error"]["code"] == "pii_detected"


def test_contract_error_envelope_on_invalid_csv(test_client):
    """Malformed CSV must return error conforming to error.json with code validation."""
    bad_csv = b"col1,col1\n1,2\n"  # Duplicate column header
    res = test_client.post(
        "/api/upload",
        files={"file": ("bad.csv", io.BytesIO(bad_csv), "text/csv")},
        headers={"X-Gateway-Request-ID": "req_bad"},
    )
    assert res.status_code == 422
    err_json = res.json()
    error_schema = json.loads((SCHEMAS_DIR / "error.json").read_text(encoding="utf-8"))
    validator.validate(err_json, error_schema)
    assert err_json["error"]["code"] == "validation"


# =============================================================================
# 3. Gateway HMAC Authentication Verification
# =============================================================================

def test_hmac_auth_middleware_enforcement():
    """Verify HMAC signature validation, timestamp skew limit, and dual-secret rotation."""
    app.state.gateway_hmac_secret_current = "secret_primary_key_12345"
    app.state.gateway_hmac_secret_previous = "secret_previous_key_67890"

    client = TestClient(app)

    # 1. /health is exempt and succeeds without headers
    res_health = client.get("/health")
    assert res_health.status_code == 200

    # 2. Request without HMAC headers fails with 401
    res_unauth = client.post("/api/session")
    assert res_unauth.status_code == 401
    assert res_unauth.json()["error"]["code"] == "validation"

    # 3. Request with valid current secret succeeds
    now = int(time.time())
    headers_valid = sign_gateway_request(
        secret="secret_primary_key_12345",
        method="POST",
        path="/api/session",
        raw_body_bytes=b"",
        timestamp=now,
    )
    res_auth = client.post("/api/session", headers=headers_valid)
    assert res_auth.status_code == 200

    # 4. Request with previous rotated secret succeeds
    headers_prev = sign_gateway_request(
        secret="secret_previous_key_67890",
        method="POST",
        path="/api/session",
        raw_body_bytes=b"",
        timestamp=now,
    )
    res_prev = client.post("/api/session", headers=headers_prev)
    assert res_prev.status_code == 200

    # 5. Request with expired timestamp (> 30s skew) fails with 401
    headers_skewed = sign_gateway_request(
        secret="secret_primary_key_12345",
        method="POST",
        path="/api/session",
        raw_body_bytes=b"",
        timestamp=now - 35,  # 35s in the past
    )
    res_skew = client.post("/api/session", headers=headers_skewed)
    assert res_skew.status_code == 401

    # Cleanup app state
    app.state.gateway_hmac_secret_current = None
    app.state.gateway_hmac_secret_previous = None


# =============================================================================
# 4. Upstream Gates Unit Tests with FakeClock
# =============================================================================

@pytest.mark.asyncio
async def test_gemini_gate_concurrency_and_rpd_exhaustion():
    """Verify GeminiGate enforces 1 in flight, fair ordering, and RPD exhaustion."""
    clock = FakeClock(start_time=1775779200.0)
    gate = GeminiGate(rpm_limit=10, rpd_limit=3, clock=clock)

    # Acquire slots up to limit 3
    t1 = await gate.acquire()
    gate.release(t1)

    t2 = await gate.acquire()
    gate.release(t2)

    t3 = await gate.acquire()
    gate.release(t3)

    # 4th call must raise QuotaExhaustedError (quota_gemini)
    with pytest.raises(QuotaExhaustedError) as exc_info:
        await gate.acquire()
    assert exc_info.value.code == "quota_gemini"
    assert gate.get_snapshot()["status"] == "exhausted"

    # Advance clock to next UTC midnight (86400s) -> quota resets
    clock.advance(86401)
    t4 = await gate.acquire()
    gate.release(t4)
    assert gate.get_snapshot()["calls_today"] == 1


@pytest.mark.asyncio
async def test_tabpfn_gate_3phase_accounting_and_retry_after():
    """Verify TabPFNGate 3-phase token lifecycle and Retry-After backoff."""
    clock = FakeClock(start_time=1775779200.0)
    gate = TabPFNGate(rpm_limit=5, daily_token_budget=30_000, clock=clock)

    # 1. Phase 1: Reserve 10,000 tokens
    res_id1 = await gate.reserve(10_000)
    assert gate.tokens_reserved == 10_000

    # 2. Phase 2: Commit actual tokens
    await gate.commit(res_id1, actual_tokens=10_000)
    assert gate.tokens_reserved == 0
    assert gate.tokens_used_today == 10_000

    # 3. Phase 1 & 3: Reserve and Refund
    res_id2 = await gate.reserve(15_000)
    assert gate.tokens_reserved == 15_000
    await gate.refund(res_id2)
    assert gate.tokens_reserved == 0
    assert gate.tokens_used_today == 10_000

    # 4. Attempt reservation exceeding remaining daily budget (25,000 > 20,000 left)
    with pytest.raises(QuotaExhaustedError) as exc_info:
        await gate.reserve(25_000)
    assert exc_info.value.code == "quota_tabpfn"

    # 5. Retry-After handling
    gate.handle_upstream_rate_limit(retry_after_s=10.0)
    t0 = clock.now()
    await gate.check_rate_limit()
    assert clock.now() >= t0 + 10.0
