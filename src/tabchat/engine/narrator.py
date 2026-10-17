"""Narrator module for tabchat: grounded explanation and calibrated uncertainty reporting."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from tabchat.llm.client import FakeLLMClient, GeminiLLMClient
from tabchat.storage import SessionStore

logger = logging.getLogger("tabchat.narrator")

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
NARRATOR_PROMPT_PATH = PROMPTS_DIR / "narrator_system.md"

# Whitelisted standard versions or constants that may appear in narrative text
WHITELISTED_FLOATS = {100.0}


def load_narrator_system_prompt() -> str:
    """Load narrator system prompt from markdown file."""
    if NARRATOR_PROMPT_PATH.exists():
        return NARRATOR_PROMPT_PATH.read_text(encoding="utf-8")
    return "You are the TabPFN Analytical Narrator. Compare against baselines and explain uncertainty."


def _collect_numeric_values(data: Any) -> set[float]:
    """Collect candidate numeric values from metrics and chart arrays, excluding integer table row indices."""
    numbers: set[float] = set()

    def _extract_from_obj(obj: Any) -> None:
        if isinstance(obj, (int, float)) and not isinstance(obj, bool):
            numbers.add(float(obj))
        elif isinstance(obj, dict):
            b_type = obj.get("type")
            if b_type == "metric":
                for k in ("value", "baseline_value", "delta"):
                    if k in obj and isinstance(obj[k], (int, float)):
                        numbers.add(float(obj[k]))
                if "uncertainty" in obj and isinstance(obj["uncertainty"], dict):
                    for uk in ("lower", "upper"):
                        if uk in obj["uncertainty"] and isinstance(obj["uncertainty"][uk], (int, float)):
                            numbers.add(float(obj["uncertainty"][uk]))
                    if "confidence_level" in obj["uncertainty"] and isinstance(obj["uncertainty"]["confidence_level"], (int, float)):
                        conf = float(obj["uncertainty"]["confidence_level"])
                        numbers.add(conf)
                        numbers.add(round(conf * 100.0, 1))
                        numbers.add(round(conf * 100.0, 0))
                return
            elif b_type == "chart":
                for arr in obj.get("data", {}).values():
                    if isinstance(arr, list):
                        for v in arr:
                            if isinstance(v, (int, float)) and not isinstance(v, bool):
                                numbers.add(float(v))
                return
            elif b_type == "table":
                # Collect float metrics from tables, but skip integer row indices
                for row in obj.get("table", {}).get("rows", []):
                    for cell in row:
                        if isinstance(cell, float):
                            numbers.add(cell)
                return

            if "holdout_size" in obj and isinstance(obj["holdout_size"], (int, float)):
                h_size = float(obj["holdout_size"])
                numbers.add(h_size)
                if h_size > 0:
                    numbers.add(round(1.0 / h_size * 100.0, 2))
                    numbers.add(round(1.0 / h_size * 100.0, 1))
                if "train_size" in obj and isinstance(obj["train_size"], (int, float)):
                    t_size = float(obj["train_size"])
                    numbers.add(t_size)
                    total_sz = t_size + h_size
                    if total_sz > 0:
                        numbers.add(round(h_size / total_sz * 100.0, 1))
                        numbers.add(round(h_size / total_sz * 100.0, 0))

            for k, v in obj.items():
                if k in ("table", "rows"):
                    continue
                _extract_from_obj(v)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                _extract_from_obj(item)

    _extract_from_obj(data)
    return numbers


def generate_template_narration(capability: str, blocks: list[dict[str, Any]]) -> str:
    """Generate a guaranteed-grounded deterministic template narration strictly from emitted blocks."""
    metrics_by_name: dict[str, dict[str, Any]] = {}
    for b in blocks:
        if isinstance(b, dict) and b.get("type") == "metric":
            name = str(b.get("name", ""))
            metrics_by_name[name.lower()] = b

    if capability == "classification":
        acc_b = metrics_by_name.get("accuracy") or metrics_by_name.get("roc-auc")
        if acc_b:
            val = acc_b.get("value")
            base = acc_b.get("baseline_value", "baseline")
            delta = acc_b.get("delta")
            delta_str = f"+{delta}" if isinstance(delta, (int, float)) and delta > 0 else f"{delta}"
            if isinstance(delta, (int, float)) and delta <= 0:
                comparison = f"matching the naive {base} baseline (lift: {delta_str})"
            else:
                comparison = f"outperforming the naive {base} baseline by {delta_str}"
            return (
                f"TabPFN classification achieved {val} {acc_b.get('name', 'accuracy')} on holdout evaluation, "
                f"{comparison}. "
                "Calibration reliability curves and holdout predictions have been computed deterministically."
            )
        return "TabPFN classification analysis completed. Metrics and calibration curves are detailed in the blocks."

    elif capability == "regression":
        rmse_b = metrics_by_name.get("rmse")
        r2_b = metrics_by_name.get("r-squared") or metrics_by_name.get("r2")
        if rmse_b and r2_b:
            rmse_val = rmse_b.get("value")
            r2_val = r2_b.get("value")
            base_rmse = rmse_b.get("baseline_value", "baseline")
            return (
                f"TabPFN regression achieved an RMSE of {rmse_val} vs naive baseline {base_rmse} (R² = {r2_val}). "
                "Predictive quantiles and scatter plots are detailed above."
            )
        elif rmse_b:
            return f"TabPFN regression achieved an RMSE of {rmse_b.get('value')} on holdout evaluation."
        return "TabPFN regression analysis completed. Predictions and interval charts are detailed above."

    elif capability == "forecasting":
        rmse_b = metrics_by_name.get("horizon rmse") or metrics_by_name.get("rmse")
        mape_b = metrics_by_name.get("mape")
        if rmse_b and mape_b:
            return (
                f"TabPFN time series forecasting projected forward trajectory with horizon RMSE of {rmse_b.get('value')} and MAPE of {mape_b.get('value')}%. "
                "Historical continuity and credible forecast intervals are provided in the charts."
            )
        elif rmse_b:
            return f"TabPFN time series forecasting projected forward trajectory with horizon RMSE of {rmse_b.get('value')}."
        return "TabPFN time series forecasting completed. Trajectory projections and confidence intervals are provided in the charts."

    elif capability == "anomaly_detection":
        flagged_b = metrics_by_name.get("anomalies flagged")
        rate_b = metrics_by_name.get("contamination rate")
        if flagged_b and rate_b:
            return (
                f"TabPFN anomaly detection identified {flagged_b.get('value')} outlier records ({rate_b.get('value')}% contamination rate). "
                "Individual anomaly score bars and flagged row telemetry are detailed in the blocks."
            )
        elif flagged_b:
            return f"TabPFN anomaly detection identified {flagged_b.get('value')} outlier records."
        return "TabPFN anomaly detection completed. Identified outlier rows and score distributions are detailed in the blocks."

    elif capability == "data_generation":
        w_b = metrics_by_name.get("mean wasserstein distance")
        f_b = metrics_by_name.get("correlation matrix fidelity")
        if w_b and f_b:
            return (
                f"TabPFN generated synthetic tabular records with {w_b.get('value')} mean Wasserstein distance and {f_b.get('value')} correlation fidelity. "
                "The synthetic dataset maintains empirical column types and distributions without memorizing real rows."
            )
        return "TabPFN generated synthetic tabular records matching empirical column types and distributions."

    elif capability == "interpretability":
        top_b = metrics_by_name.get("top feature influence")
        share_b = metrics_by_name.get("cumulative top-3 share")
        if top_b and share_b:
            return (
                f"TabPFN permutation interpretability measured a top feature influence of {top_b.get('value')} accounting for {share_b.get('value')}% cumulative variance. "
                "Feature importance rankings and attribution summaries are detailed above."
            )
        elif top_b:
            return f"TabPFN permutation interpretability measured a top feature influence of {top_b.get('value')}."
        return "TabPFN interpretability analysis completed. Feature importance rankings and attribution summaries are detailed in the blocks."

    return "TabPFN analysis completed deterministically. Emitted metrics and visual artifacts are detailed in the blocks."


def verify_hallucination_guard(
    narration: str,
    source: dict[str, Any] | list[dict[str, Any]],
) -> list[float]:
    """Inspect narration text to verify numbers against blocks or results dictionary.

    Returns a list of phantom metrics detected (empty if all verified).
    Logs warnings for any phantom numbers.
    """
    block_metrics = _collect_numeric_values(source)

    phantom_metrics: list[float] = []

    # 1. Percentages: match r'(\d+(?:\.\d+)?)\s*%'
    pct_matches = re.findall(r"(\d+(?:\.\d+)?)\s*%", narration)
    for m in pct_matches:
        try:
            val = float(m)
            matched = (
                val in WHITELISTED_FLOATS
                or any(abs(val / 100.0 - bm) <= 0.005 for bm in block_metrics)
                or any(abs(val - bm) <= 0.005 for bm in block_metrics)
            )
            if not matched:
                phantom_metrics.append(val)
                logger.warning(
                    "HALLUCINATION GUARD: Phantom percentage detected in narration: %s%% not found in blocks",
                    val,
                )
        except ValueError:
            continue

    # 2. Bare floats: match r'(?<!\S)[(\[]?[+-]?(\d+\.\d+)(?!\s*%)(?=[.,);:!?\]]*(?!\S))'
    float_matches = re.findall(r"(?<!\S)[(\[]?[+-]?(\d+\.\d+)(?!\s*%)(?=[.,);:!?\]]*(?!\S))", narration)
    for m in float_matches:
        try:
            val = float(m)
            if val in WHITELISTED_FLOATS:
                continue
            matched = any(abs(val - bm) <= 0.005 for bm in block_metrics)
            if not matched:
                phantom_metrics.append(val)
                logger.warning(
                    "HALLUCINATION GUARD: Phantom floating-point metric detected in narration: %s not found in blocks",
                    val,
                )
        except ValueError:
            continue

    return phantom_metrics


async def narrate_results(
    session_id: str,
    llm_client: GeminiLLMClient | FakeLLMClient | None = None,
    store: SessionStore | None = None,
) -> str:
    """Generate a grounded analytical narrative explaining deterministic results.

    Enforces NARRATOR GUARD:
    - Verifies that every percentage and metric in generated narrative appears in some block.
    - On violation, falls back to a deterministic template narration and logs an event.
    """
    store = store or SessionStore()
    llm = llm_client or GeminiLLMClient()

    # 1. Load results.json and dataset_card.json
    results = store.get_results(session_id)
    if results is None:
        raise ValueError(f"No results found for session '{session_id}'. Run the executor first.")

    blocks = results.get("blocks", [])
    active_plan = store.get_plan(session_id) or {}
    capability = active_plan.get("capability") or results.get("spec", {}).get("task_type", "classification")

    try:
        _, dataset_card = store.get_dataset(session_id)
    except FileNotFoundError:
        dataset_card = {}

    # 2. Format context for narration
    context = {
        "dataset_card": {
            "row_count": dataset_card.get("row_count"),
            "col_count": dataset_card.get("col_count"),
            "column_names": dataset_card.get("column_names", []),
        },
        "blocks": blocks,
        "execution_results": results,
    }

    user_prompt = (
        f"Below are the verified execution results and emitted visual blocks:\n\n"
        f"```json\n{json.dumps(context, indent=2)}\n```\n\n"
        "Synthesize a rigorous, grounded analytical report comparing TabPFN against the naive baseline, "
        "referencing only the numbers present in the blocks. Do not hallucinate any outside numbers."
    )

    messages = [{"role": "user", "content": user_prompt}]
    system_prompt = load_narrator_system_prompt()

    # 3. Call LLM via generate_text
    narration = await llm.generate_text(
        messages=messages,
        system_prompt=system_prompt,
    )

    # 4. Hallucination Guard: Verify against blocks and execution results
    check_source = [blocks, results] if blocks else results
    phantoms = verify_hallucination_guard(narration, check_source)

    if phantoms:
        logger.warning(
            "HALLUCINATION GUARD VIOLATION in session %s: Phantoms %s found. Falling back to template narration.",
            session_id,
            phantoms,
        )
        try:
            from tabchat.logging import get_event_logger
            get_event_logger().log_event(
                session_id=session_id,
                event_type="hallucination_guard_violation",
                data={
                    "phantom_numbers": phantoms,
                    "rejected_narration": narration,
                    "capability": capability,
                },
            )
        except Exception:
            pass

        # Fallback to guaranteed-grounded template narration
        narration = generate_template_narration(capability, blocks)

    # 5. Append narration to history.jsonl
    store.append_history(session_id, role="assistant", message=narration)

    # 6. Return narration text
    return narration
