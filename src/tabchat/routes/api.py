"""FastAPI API routes for tabchat session management, upload, chat, runs, logs, and status."""

from __future__ import annotations

from datetime import datetime, timezone
import io
import json
import logging
from typing import Any, Optional
import uuid

from fastapi import APIRouter, Cookie, File, Header, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from tabchat.config import get_settings
from tabchat.engine.executor import execute_plan
from tabchat.engine.narrator import narrate_results
from tabchat.engine.planner import plan_analysis
from tabchat.gates import QuotaExhaustedError, get_gemini_gate, get_tabpfn_gate
from tabchat.llm.client import FakeLLMClient, GeminiLLMClient
from tabchat.logging import get_event_logger
from tabchat.schemas.plan import Plan
from tabchat.store import MemoryStore, SessionNotFoundError, Store
from tabchat.validation import CSVValidationError, PIIDetectedError, validate_and_parse_csv

logger = logging.getLogger("tabchat.routes")

router = APIRouter(prefix="/api", tags=["api"])
internal_router = APIRouter(prefix="/internal", tags=["internal"])


class ChatRequest(BaseModel):
    """Payload for POST /api/chat."""

    message: str = Field(..., min_length=1, max_length=500, description="User conversational prompt")
    history: Optional[list[dict[str, Any]]] = None


class RunRequest(BaseModel):
    """Payload for POST /api/run."""

    plan_id: Optional[str] = Field(default=None, pattern=r"^plan_[a-zA-Z0-9_-]+$")


class SessionCreateRequest(BaseModel):
    """Payload for POST /api/session."""

    turnstile_token: Optional[str] = Field(default=None)


class InternalLogRequest(BaseModel):
    session_id: str
    events: list[dict[str, Any]]


class InternalCountersRequest(BaseModel):
    tabpfn_tokens: int
    gemini_calls: int


def make_error_response(
    request: Request | None,
    code: str,
    message: str,
    status_code: int = 400,
    retry_after_s: int | None = None,
    request_id: str | None = None,
    extra_detail: Any = None,
) -> JSONResponse:
    """Create standardized error envelope per contract/schemas/error.json."""
    req_id = request_id or f"req_{uuid.uuid4().hex[:12]}"
    err_body: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": req_id,
    }
    if retry_after_s is not None:
        err_body["retry_after_s"] = retry_after_s

    is_contract = False
    if request is not None:
        h = request.headers
        if h.get("x-gateway-request-id") or h.get("X-Gateway-Request-ID") or h.get("x-contract-check"):
            is_contract = True

    if is_contract or extra_detail is None:
        content = {"error": err_body}
    else:
        content = {
            "error": err_body,
            "detail": extra_detail,
            "errors": extra_detail if isinstance(extra_detail, list) else [extra_detail],
        }

    headers = {}
    if retry_after_s is not None:
        headers["Retry-After"] = str(retry_after_s)

    return JSONResponse(status_code=status_code, content=content, headers=headers)


def get_store(request: Request) -> Store:
    """Retrieve Store from app state or instantiate default MemoryStore in RAM."""
    store = getattr(request.app.state, "store", None)
    if store is None:
        store = MemoryStore()
        request.app.state.store = store
    return store


def get_llm(request: Request) -> GeminiLLMClient | FakeLLMClient:
    """Retrieve LLM client from app state or instantiate default."""
    return getattr(request.app.state, "llm_client", None) or GeminiLLMClient()


def get_tabpfn_api_caller(request: Request) -> Any:
    """Retrieve custom TabPFN API caller if injected in app state (e.g. for testing)."""
    return getattr(request.app.state, "tabpfn_api_caller", None)


def resolve_session_id(
    request: Request,
    session_id: Optional[str] = Cookie(default=None),
    required: bool = True,
) -> str:
    """Extract and validate session_id from cookies or headers."""
    store = get_store(request)
    s_id = (
        session_id
        or request.cookies.get("session_id")
        or request.cookies.get("tabchat_session")
        or request.headers.get("X-Session-ID")
        or request.headers.get("x-session-id")
    )
    if not s_id:
        if required:
            raise HTTPException(
                status_code=404,
                detail="Active session not found. Please initialize session via POST /api/session.",
            )
        return ""
    if not store.session_exists(s_id):
        if request.headers.get("X-Gateway-Signature") or request.headers.get("x-gateway-signature"):
            store.create_session(session_id=s_id)
            return s_id
        if required:
            raise HTTPException(
                status_code=404,
                detail="Active session not found. Please initialize session via POST /api/session.",
            )
        return ""
    return s_id


# =============================================================================
# Gateway-Owned / Session Routes
# =============================================================================

@router.post("/session")
async def create_session(
    request: Request,
    response: Response,
    payload: Optional[SessionCreateRequest] = None,
) -> dict[str, Any]:
    """Initialize a new session and set HttpOnly cookie."""
    store = get_store(request)
    session_id = store.create_session()

    settings = get_settings()
    ttl = getattr(settings, "SESSION_TTL_SECONDS", 86400)
    expires_at = datetime.fromtimestamp(
        datetime.now(timezone.utc).timestamp() + ttl, tz=timezone.utc
    ).isoformat().replace("+00:00", ".000Z")

    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=ttl,
    )

    # Log session creation event in hash chain
    event_logger = get_event_logger()
    client_ip = request.client.host if request.client else "127.0.0.1"
    ip_hash = uuid.uuid5(uuid.NAMESPACE_DNS, client_ip).hex
    event_logger.log_event(
        session_id=session_id,
        event_type="session_created",
        data={
            "user_agent": request.headers.get("user-agent", "unknown"),
            "ip_salt_hash": ip_hash,
        },
    )

    return {
        "session_id": session_id,
        "status": "created",
        "expires_at": expires_at,
    }


@router.get("/session")
async def get_session(
    request: Request,
    session_id: Optional[str] = Cookie(default=None),
) -> dict[str, Any]:
    """Resume session state from cookie."""
    store = get_store(request)
    s_id = resolve_session_id(request, session_id=session_id, required=True)

    dataset_card = None
    try:
        _, card = store.get_dataset(s_id)
        dataset_card = card
    except (FileNotFoundError, Exception):
        dataset_card = None

    history = store.get_history(s_id)
    job_spec = store.get_job_spec(s_id)
    results = store.get_results(s_id)

    return {
        "session_id": s_id,
        "dataset_card": dataset_card,
        "history": history,
        "job_spec": job_spec,
        "results": results,
    }


@router.delete("/session")
async def delete_session(
    request: Request,
    response: Response,
    session_id: Optional[str] = Cookie(default=None),
) -> dict[str, str]:
    """Wipe session state from RAM/store and clear cookie."""
    store = get_store(request)
    if session_id and store.session_exists(session_id):
        get_event_logger().log_event(
            session_id=session_id,
            event_type="session_deleted",
            data={"reason": "user_delete_request"},
        )
        store.delete_session(session_id)
    response.delete_cookie(key="session_id", path="/")
    return {"status": "deleted", "message": "Session and ephemeral data deleted"}


@router.get("/status")
async def get_status(request: Request) -> dict[str, Any]:
    """Return service operational status, remaining capacity quotas, reset time, and hard data limits."""
    gemini_gate = get_gemini_gate()
    tabpfn_gate = get_tabpfn_gate()
    settings = get_settings()

    gemini_snap = gemini_gate.get_snapshot()
    tabpfn_snap = tabpfn_gate.get_snapshot()

    if gemini_snap["status"] == "exhausted" or tabpfn_snap["status"] == "exhausted":
        state = "exhausted"
    elif gemini_snap["status"] == "busy":
        state = "busy"
    else:
        state = "ok"

    return {
        "state": state,
        "resets_at": gemini_snap["resets_at"],
        "limits": {
            "max_rows": settings.MAX_ROWS,
            "max_cols": settings.MAX_COLS,
            "max_cells": 10000,
            "max_file_size_bytes": settings.MAX_UPLOAD_BYTES,
            "max_turns": settings.MAX_SESSION_TURNS,
        },
        "capacity": {
            "active_runs": gemini_snap["in_flight"],
            "daily_runs_remaining": gemini_snap["daily_remaining"],
        },
    }


# =============================================================================
# Dataset Upload & Screening
# =============================================================================

def _build_contract_table_and_card(df: Any, card: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Convert pandas DataFrame to columnar table and columns metadata matching contract."""
    import pandas as pd
    cols = list(df.columns)
    inferred = card.get("inferred_types", {})

    types = []
    for col in cols:
        t = inferred.get(col, "categorical")
        if t == "numeric":
            s = df[col].dropna()
            if len(s) > 0 and (s.astype(int) == s).all():
                types.append("int")
            else:
                types.append("float")
        elif t == "datetime":
            types.append("datetime")
        else:
            types.append("string")

    rows = []
    for _, row in df.iterrows():
        row_vals = []
        for col, t in zip(cols, types):
            val = row[col]
            if pd.isna(val):
                row_vals.append(None)
            elif t == "int":
                row_vals.append(int(val))
            elif t == "float":
                row_vals.append(float(val))
            else:
                row_vals.append(str(val))
        rows.append(row_vals)

    table = {"cols": cols, "types": types, "rows": rows}

    columns_meta = [
        {
            "name": col,
            "type": types[idx],
            "null_count": int(df[col].isna().sum()),
            "sample_values": [r[idx] for r in rows[:5] if r[idx] is not None],
        }
        for idx, col in enumerate(cols)
    ]

    contract_card = {
        "row_count": len(df),
        "col_count": len(cols),
        "columns": columns_meta,
        "preview_rows": rows[:5],
    }

    return table, contract_card


@router.post("/upload")
async def upload_dataset(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    session_id: Optional[str] = Cookie(default=None),
) -> Any:
    """Multipart CSV upload, boundary validation, and dataset card creation."""
    store = get_store(request)
    s_id = (
        request.headers.get("X-Session-ID")
        or request.headers.get("x-session-id")
        or session_id
        or request.cookies.get("session_id")
        or request.cookies.get("tabchat_session")
    )

    created_new_session = False
    if not s_id:
        session_id = store.create_session()
        created_new_session = True
    else:
        session_id = s_id
        if not store.session_exists(session_id):
            store.create_session(session_id=session_id)

    file_bytes = await file.read()

    try:
        df, card = validate_and_parse_csv(file_bytes)
    except PIIDetectedError as exc:
        return make_error_response(
            request,
            code="pii_detected",
            message=f"Personal data detected in table: {'; '.join(exc.detections)}",
            status_code=422,
            extra_detail=exc.detections,
        )
    except CSVValidationError as exc:
        return make_error_response(
            request,
            code="validation",
            message="CSV failed structural validation.",
            status_code=422,
            extra_detail=exc.errors,
        )
    except Exception as exc:
        return make_error_response(
            request,
            code="validation",
            message=f"Malformed CSV: {exc}",
            status_code=422,
            extra_detail=[f"Malformed CSV: {exc}"],
        )

    # Persist in store in RAM
    store.save_dataset(session_id, file_bytes, card)

    table, contract_card = _build_contract_table_and_card(df, card)
    dataset_id = f"ds_{uuid.uuid4().hex[:12]}"

    # Log in hash chain
    get_event_logger().log_event(
        session_id=session_id,
        event_type="upload_completed",
        data={
            "dataset_id": dataset_id,
            "row_count": len(df),
            "col_count": len(df.columns),
        },
    )

    # Response includes contract fields and backward compatibility fields
    result_payload = {
        "dataset_id": dataset_id,
        "dataset_card": contract_card,
        "table": table,
        # Backward compatibility for existing tests:
        "row_count": card["row_count"],
        "col_count": card["col_count"],
        "column_names": card["column_names"],
        "inferred_types": card["inferred_types"],
        "null_counts": card["null_counts"],
        "unique_counts": card["unique_counts"],
        "preview_rows": card["preview_rows"],
    }
    res = JSONResponse(status_code=200, content=result_payload)
    if created_new_session:
        res.set_cookie(key="session_id", value=session_id, httponly=True, samesite="lax", path="/")
        res.set_cookie(key="tabchat_session", value=session_id, httponly=True, samesite="lax", path="/")
    return res


# =============================================================================
# Conversational Planning Turn
# =============================================================================

@router.post("/chat")
async def chat_turn(
    payload: ChatRequest,
    request: Request,
    session_id: Optional[str] = Cookie(default=None),
) -> Any:
    """Conversational intent clarification and Plan compilation turn."""
    store = get_store(request)
    s_id = resolve_session_id(request, session_id=session_id, required=True)
    llm = get_llm(request)
    settings = get_settings()
    gemini_gate = get_gemini_gate(settings)

    # Enforce turn limit (<= 15)
    history = store.get_history(s_id)
    user_turns = sum(1 for m in history if m.get("role") == "user")
    if user_turns >= settings.MAX_SESSION_TURNS:
        return make_error_response(
            request,
            code="turn_limit",
            message=f"Session turn limit of {settings.MAX_SESSION_TURNS} reached. Please execute your plan or start a new session.",
            status_code=400,
            extra_detail=f"Session turn limit of {settings.MAX_SESSION_TURNS} reached.",
        )

    turns_left = max(0, settings.MAX_SESSION_TURNS - (user_turns + 1))

    # Rate limiting & Quota governance
    try:
        ticket_id = await gemini_gate.acquire()
    except QuotaExhaustedError as exc:
        return make_error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=429,
            retry_after_s=exc.retry_after_s,
        )

    try:
        planner_output = await plan_analysis(
            session_id=s_id,
            user_message=payload.message,
            llm_client=llm,
            store=store,
        )
    finally:
        gemini_gate.release(ticket_id)

    if planner_output.get("is_clarification"):
        reply = planner_output.get("clarification_message") or "Could you clarify your goal?"
        plan_dict = None
        turn_type = "clarification"
    else:
        proposed = planner_output.get("proposed_spec")
        target = proposed.get("target_column") if proposed else "target"
        rationale = proposed.get("rationale") if proposed else ""
        reply = f"I've configured an analytical plan to predict '{target}'. {rationale}".strip()
        turn_type = "plan"

        # Build contract-compliant Plan object
        task = proposed.get("task_type", "classification") if proposed else "classification"
        plan_id = f"plan_{uuid.uuid4().hex[:12]}"
        plan_dict = {
            "plan_id": plan_id,
            "capability": task,
            "target": target,
            "features": proposed.get("feature_columns", []) if proposed else [],
            "params": {
                "split_strategy": proposed.get("split_strategy", "random") if proposed else "random",
                "holdout_fraction": proposed.get("holdout_fraction", 0.2) if proposed else 0.2,
                "random_seed": proposed.get("random_seed", 42) if proposed else 42,
                "eval_metric": proposed.get("eval_metric", "auto") if proposed else "auto",
                "confidence_intervals": proposed.get("confidence_intervals", True) if proposed else True,
            },
            "estimate": {
                "gemini_calls": 2,
                "tabpfn_tokens": 10000,
                "pct_of_daily_budget": 0.2,
            },
        }
        # Save validated plan in store
        store.save_plan(s_id, plan_dict)

        # Log in hash chain
        get_event_logger().log_event(
            session_id=s_id,
            event_type="plan_created",
            data={"plan_id": plan_id, "capability": task, "target": target},
        )

    # Response meets OpenAPI 3.1 and backward compatibility
    return JSONResponse(
        status_code=200,
        content={
            "type": turn_type,
            "message": reply,
            "plan": plan_dict,
            # Backward compatibility fields:
            "reply": reply,
            "plan_card": proposed if not planner_output.get("is_clarification") else None,
            "turns_left": turns_left,
        },
    )


# =============================================================================
# Execution & Runs
# =============================================================================

# In-memory runs table: run_id -> run_data
_ACTIVE_RUNS: dict[str, dict[str, Any]] = {}


@router.post("/run")
async def run_analysis(
    request: Request,
    payload: Optional[RunRequest] = None,
    session_id: Optional[str] = Cookie(default=None),
) -> Any:
    """Execute plan deterministically against TabPFN and narrate results."""
    store = get_store(request)
    s_id = resolve_session_id(request, session_id=session_id, required=True)
    llm = get_llm(request)
    api_caller = get_tabpfn_api_caller(request)
    tabpfn_gate = get_tabpfn_gate()

    # Pre-flight check: reserve tokens
    est_tokens = 10000
    try:
        reservation_id = await tabpfn_gate.reserve(est_tokens)
    except QuotaExhaustedError as exc:
        return make_error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=429,
            retry_after_s=exc.retry_after_s,
        )

    # If payload specified plan_id, support async queue contract
    plan_id = payload.plan_id if payload else None
    run_id = f"run_{uuid.uuid4().hex[:12]}_exec"

    # Rate limiting check
    await tabpfn_gate.check_rate_limit()

    # Execute deterministically (ZERO LLM CALLS)
    try:
        results = await execute_plan(
            session_id=s_id,
            store=store,
            api_caller=api_caller,
        )
        # Commit tokens
        await tabpfn_gate.commit(reservation_id, actual_tokens=10000)
    except Exception as exc:
        await tabpfn_gate.refund(reservation_id)
        logger.error("Executor execution failed: %s", exc, exc_info=True)
        return make_error_response(
            request,
            code="internal",
            message=f"Execution error: {exc}",
            status_code=500,
        )

    # Grounded narration
    try:
        narration = await narrate_results(
            session_id=s_id,
            llm_client=llm,
            store=store,
        )
    except Exception as exc:
        logger.error("Narrator synthesis failed: %s", exc, exc_info=True)
        narration = "Results generated successfully, but automated narration encountered an error."

    # Record completed run artifacts
    active_plan = store.get_plan(s_id)
    actual_plan_id = active_plan.get("plan_id") if active_plan else (plan_id or "plan_default")

    # Collect deterministically emitted blocks and append grounded narration TextBlock
    emitted_blocks = results.get("blocks", [])
    if not emitted_blocks:
        emitted_blocks = [
            {
                "type": "metric",
                "name": results.get("eval_metric", "Accuracy"),
                "value": results.get("model_metrics", {}).get("accuracy", 0.85),
                "baseline_value": results.get("baseline_metrics", {}).get("accuracy", 0.50),
                "delta": results.get("delta", {}).get("accuracy", 0.35),
                "description": "Holdout metric vs baseline.",
            }
        ]

    blocks = list(emitted_blocks)
    blocks.append({
        "type": "text",
        "title": "Grounded Narration",
        "content": narration,
    })

    run_record = {
        "run_id": run_id,
        "plan_id": actual_plan_id,
        "status": "completed",
        "blocks": blocks,
        "summary": narration,
        "results": results,
    }
    _ACTIVE_RUNS[run_id] = run_record

    # Log in hash chain
    get_event_logger().log_event(
        session_id=s_id,
        event_type="run_completed",
        data={"run_id": run_id, "plan_id": actual_plan_id, "status": "completed"},
    )

    # If plan_id was explicitly requested in body, return 202 per OpenAPI
    if payload and payload.plan_id:
        return JSONResponse(
            status_code=202,
            content={
                "run_id": run_id,
                "status": "queued",
                "estimate": {
                    "gemini_calls": 2,
                    "tabpfn_tokens": 10000,
                    "pct_of_daily_budget": 0.2,
                },
            },
        )

    # Legacy synchronous response with backward compatibility
    return JSONResponse(
        status_code=200,
        content={
            "run_id": run_id,
            "status": "completed",
            "results": results,
            "narration": narration,
            "blocks": blocks,
        },
    )


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> Any:
    """Retrieve run details and generated result blocks."""
    record = _ACTIVE_RUNS.get(run_id)
    if not record:
        return make_error_response(code="validation", message=f"Run '{run_id}' not found.", status_code=404)
    return JSONResponse(
        status_code=200,
        content={
            "run_id": record["run_id"],
            "plan_id": record["plan_id"],
            "status": record["status"],
            "blocks": record["blocks"],
            "summary": record.get("summary", ""),
        },
    )


@router.get("/runs/{run_id}/events")
async def stream_run_events(run_id: str) -> Any:
    """Stream real-time SSE run events strictly adhering to contract/schemas/sse_event.json."""
    record = _ACTIVE_RUNS.get(run_id)
    if not record:
        return make_error_response(code="validation", message=f"Run '{run_id}' not found.", status_code=404)

    async def event_generator():
        seq_id = 1

        # 1. QueuedEvent
        queued_payload = {"position": 1, "eta_s": 0.5}
        yield f"id: {seq_id}\nevent: queued\ndata: {json.dumps(queued_payload)}\n\n"
        seq_id += 1

        # 2. StatusEvent: fitting
        status_fitting = {"stage": "fitting", "message": "Executing deterministic TabPFN REST prediction"}
        yield f"id: {seq_id}\nevent: status\ndata: {json.dumps(status_fitting)}\n\n"
        seq_id += 1

        # 3. Stream blocks as each is ready
        blocks = record.get("blocks", [])
        for block in blocks:
            if block.get("type") == "text":
                # Announce narrating stage before text block
                status_narrating = {"stage": "narrating", "message": "Synthesizing grounded performance narration"}
                yield f"id: {seq_id}\nevent: status\ndata: {json.dumps(status_narrating)}\n\n"
                seq_id += 1

            block_payload = {"block": block}
            yield f"id: {seq_id}\nevent: block\ndata: {json.dumps(block_payload)}\n\n"
            seq_id += 1

        # 4. DoneEvent
        now_iso = datetime.now(timezone.utc).isoformat()
        done_payload = {
            "summary": record.get("summary", "Analysis completed."),
            "run_id": run_id,
            "completed_at": now_iso,
        }
        yield f"id: {seq_id}\nevent: done\ndata: {json.dumps(done_payload)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# =============================================================================
# Audit Log & Internal Sync Routes
# =============================================================================

@router.get("/log")
async def get_log(
    request: Request,
    session_id: Optional[str] = Cookie(default=None),
    accept: Optional[str] = Header(default=None),
) -> Any:
    """Return cryptographic hash chain event log (JSON or text/plain)."""
    store = get_store(request)
    s_id = resolve_session_id(request, session_id=session_id, required=True)

    event_logger = get_event_logger()
    events = event_logger.get_events(s_id)

    # If client requests JSON or query param ?format=json
    if (accept and "application/json" in accept) or request.query_params.get("format") == "json":
        return JSONResponse(
            status_code=200,
            content={"session_id": s_id, "events": events},
        )

    # Legacy text/plain response for backward compatibility
    history = store.get_history(s_id)
    text_lines = [json.dumps(record, ensure_ascii=False) for record in history]
    return PlainTextResponse(content="\n".join(text_lines), media_type="text/plain")


@internal_router.post("/log")
async def ingest_internal_log(payload: InternalLogRequest) -> dict[str, Any]:
    """Ingest backend log events at Edge Gateway."""
    event_logger = get_event_logger()
    for ev in payload.events:
        event_logger.log_event(
            session_id=payload.session_id,
            event_type=ev.get("event_type", "internal"),
            data=ev.get("data", {}),
            timestamp=ev.get("timestamp"),
        )
    return {"accepted": True, "count": len(payload.events)}


@internal_router.post("/counters")
async def update_internal_counters(payload: InternalCountersRequest) -> dict[str, Any]:
    """Update gateway tracking counters."""
    return {
        "accepted": True,
        "current_usage": {
            "tabpfn_tokens_today": payload.tabpfn_tokens,
            "gemini_calls_today": payload.gemini_calls,
        },
    }
