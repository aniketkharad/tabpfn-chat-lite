"""Deterministic executor module for tabchat: executes Plan with ZERO LLM calls.

Invariants:
- Accepts only a Plan that validates against the contract (contract/schemas/plan.json).
- Zero LLM calls during execution.
- Interacts with Store abstraction without assuming POSIX disk paths.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from tabchat.engine.emitters import emit_blocks_for_capability
from tabchat.schemas.job_spec import JobSpec
from tabchat.schemas.plan import Plan
from tabchat.services.tabpfn_runner import run_tabpfn_job
from tabchat.store import Store
from tabchat.storage import SessionStore

logger = logging.getLogger("tabchat.executor")


def validate_plan_contract(plan_data: dict[str, Any]) -> Plan:
    """Validate that plan conforms strictly to contract/schemas/plan.json."""
    try:
        return Plan.model_validate(plan_data)
    except Exception as exc:
        raise ValueError(f"Plan validation failed against contract: {exc}") from exc


async def execute_plan(
    session_id: str,
    store: Store | None = None,
    api_caller: Callable[..., dict[str, Any]] | None = None,
    plan_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute a validated Plan deterministically against TabPFN.

    STRICT MANDATE: ZERO LLM CALLS.
    Steps:
    1. Validate Plan against contract schema.
    2. Retrieve dataset DataFrame and raw bytes from Store in RAM.
    3. Invoke deterministic TabPFN runner.
    4. Save returned result dictionary to Store.
    5. Return results dict.
    """
    store = store or SessionStore()

    # 1. Load and validate Plan / JobSpec
    raw_plan = plan_override or store.get_plan(session_id)
    if raw_plan is None:
        # Fall back to job_spec for backward compatibility with legacy tests
        raw_spec = store.get_job_spec(session_id)
        if raw_spec is None:
            raise ValueError(
                f"No plan found for session '{session_id}'. Please define a plan before running."
            )
        # Synthesize contract-adherent Plan from JobSpec
        task = raw_spec.get("task_type", "classification")
        target = raw_spec.get("target_column")
        features = raw_spec.get("feature_columns", [])
        params = {
            "split_strategy": raw_spec.get("split_strategy", "random"),
            "holdout_fraction": raw_spec.get("holdout_fraction", 0.2),
            "random_seed": raw_spec.get("random_seed", 42),
            "eval_metric": raw_spec.get("eval_metric", "auto"),
            "confidence_intervals": raw_spec.get("confidence_intervals", True),
        }
        raw_plan = {
            "plan_id": f"plan_{session_id[:16]}",
            "capability": task,
            "target": target,
            "features": features,
            "params": params,
            "estimate": {
                "gemini_calls": 2,
                "tabpfn_tokens": 10000,
                "pct_of_daily_budget": 0.2,
            },
        }

    # Contract boundary validation
    plan = validate_plan_contract(raw_plan)

    # 2. Retrieve dataset DataFrame and raw bytes via Store
    df, _ = store.get_dataset(session_id)
    try:
        raw_bytes = store.get_raw_bytes(session_id)
    except (AttributeError, FileNotFoundError):
        # Fallback if store is custom or older disk store
        raw_path = getattr(store, "sessions_dir", None)
        if raw_path and (raw_path / session_id / "raw.csv").exists():
            raw_bytes = (raw_path / session_id / "raw.csv").read_bytes()
        else:
            raw_bytes = df.to_csv(index=False).encode("utf-8")

    # Map Plan to JobSpec for runner execution
    spec = JobSpec(
        task_type="regression" if plan.capability == "regression" else "classification",
        target_column=plan.target or (list(df.columns)[-1] if len(df.columns) > 0 else "target"),
        feature_columns=plan.features or [c for c in df.columns if c != plan.target],
        excluded_columns=[],
        split_strategy=plan.params.get("split_strategy", "random"),
        split_column=plan.params.get("split_column"),
        holdout_fraction=plan.params.get("holdout_fraction", 0.2),
        random_seed=plan.params.get("random_seed", 42),
        eval_metric=plan.params.get("eval_metric", "auto"),
        confidence_intervals=plan.params.get("confidence_intervals", True),
        rationale=f"Executing {plan.capability} plan for {plan.target}.",
    )

    # 3. Invoke deterministic TabPFN runner (Zero LLM calls)
    logger.info("Executing deterministic plan for session %s (capability: %s)", session_id, plan.capability)
    cache_dir = None
    if hasattr(store, "data_dir") and getattr(store, "data_dir") is not None:
        cache_dir = getattr(store, "data_dir") / "cache" / "tabpfn"

    results = await run_tabpfn_job(
        spec=spec,
        df=df,
        raw_bytes=raw_bytes,
        cache_dir=cache_dir,
        api_caller=api_caller,
    )

    # 4. Deterministically emit ResultBlocks for capability (ZERO LLM CALLS)
    blocks = emit_blocks_for_capability(
        capability=plan.capability,
        spec=spec,
        df=df,
        results=results,
    )
    results["blocks"] = blocks

    # 5. Save returned result dictionary
    store.save_results(session_id, results)

    # 6. Return results dict
    return results
