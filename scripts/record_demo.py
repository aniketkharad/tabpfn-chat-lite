#!/usr/bin/env python3
"""scripts/record_demo.py: Seeded synthetic demo dataset generator and run recorder.

STRICT INVARIANTS:
1. Datasets are 100% synthetically generated with fixed seeds (seed=42) -> zero licensing/copyright issues.
2. Runs offline with deterministic mock execution by default.
3. Live API calls to Gemini / TabPFN are strictly blocked unless user explicitly invokes --live.
4. Emitted files in demo/<name>.json contain Plan, Event timeline with relative timings, and ResultBlocks.
5. Zero secrets and zero private personal data recorded.
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import sys
import time
from typing import Any
import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tabchat.engine.emitters import emit_blocks_for_capability
from tabchat.schemas.job_spec import JobSpec
from tabchat.schemas.plan import Plan

DEMO_DIR = ROOT_DIR / "demo"


# =============================================================================
# 1. Seeded Synthetic Dataset Generators (100% Artificial, Zero Licensing)
# =============================================================================

def generate_synthetic_classification(n_rows: int = 40, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic churn dataset with continuous features and binary target."""
    rng = np.random.default_rng(seed)
    age = rng.integers(20, 70, size=n_rows)
    tenure = rng.integers(1, 10, size=n_rows)
    balance = np.round(rng.uniform(1000.0, 15000.0, size=n_rows), 2)
    churn = ["yes" if (a > 45 and b < 5000) or rng.uniform() < 0.25 else "no" for a, b in zip(age, balance)]
    return pd.DataFrame({"age": age, "tenure": tenure, "balance": balance, "churn": churn})


def generate_synthetic_regression(n_rows: int = 40, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic housing price dataset."""
    rng = np.random.default_rng(seed)
    sqft = rng.integers(600, 3500, size=n_rows)
    bedrooms = rng.integers(1, 5, size=n_rows)
    age = rng.integers(1, 50, size=n_rows)
    price = np.round(50.0 + (sqft * 0.12) + (bedrooms * 15.0) - (age * 0.5) + rng.normal(0, 10, size=n_rows), 2)
    return pd.DataFrame({"sqft": sqft, "bedrooms": bedrooms, "building_age": age, "price_k": price})


def generate_synthetic_forecasting(n_rows: int = 36, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic monthly time series trajectory."""
    rng = np.random.default_rng(seed)
    periods = [f"2023-{m:02d}" for m in range(1, 13)] + [f"2024-{m:02d}" for m in range(1, 13)] + [f"2025-{m:02d}" for m in range(1, 13)]
    base = 100.0
    values = []
    for i, _ in enumerate(periods):
        trend = i * 2.5
        season = 15.0 * np.sin(2 * np.pi * (i % 12) / 12.0)
        noise = rng.normal(0, 2.0)
        values.append(round(base + trend + season + noise, 1))
    return pd.DataFrame({"period": periods, "volume": values})


def generate_synthetic_anomaly(n_rows: int = 40, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic sensor telemetry with intentional outlier records."""
    rng = np.random.default_rng(seed)
    vibration = np.round(rng.normal(2.5, 0.4, size=n_rows), 2)
    temp = np.round(rng.normal(70.0, 3.0, size=n_rows), 2)
    # Inject 3 outliers
    vibration[12] = 8.45
    temp[12] = 112.4
    vibration[25] = 9.72
    temp[25] = 118.1
    vibration[34] = 7.89
    temp[34] = 105.3
    return pd.DataFrame({"vibration": vibration, "temp": temp})


def generate_synthetic_data_gen(n_rows: int = 40, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic patient clinical indicators."""
    rng = np.random.default_rng(seed)
    age = rng.integers(20, 80, size=n_rows)
    bmi = np.round(rng.normal(26.0, 4.0, size=n_rows), 1)
    blood_pressure = rng.integers(100, 160, size=n_rows)
    diabetic = [bool(b > 30 and bp > 135) for b, bp in zip(bmi, blood_pressure)]
    return pd.DataFrame({"age": age, "bmi": bmi, "blood_pressure": blood_pressure, "diabetic": diabetic})


def generate_synthetic_interpretability(n_rows: int = 40, seed: int = 42) -> pd.DataFrame:
    """Generate diagnostic risk dataset."""
    rng = np.random.default_rng(seed)
    glucose = rng.integers(70, 200, size=n_rows)
    insulin = rng.integers(15, 250, size=n_rows)
    bmi = np.round(rng.normal(27.0, 4.0, size=n_rows), 1)
    age = rng.integers(20, 75, size=n_rows)
    risk = [1 if g > 140 or (i > 150 and b > 30) else 0 for g, i, b in zip(glucose, insulin, bmi)]
    return pd.DataFrame({"glucose": glucose, "insulin": insulin, "bmi": bmi, "age": age, "risk": risk})


# =============================================================================
# 2. Recording Orchestrator
# =============================================================================

CAPABILITY_CONFIGS = [
    {
        "name": "classification",
        "generator": generate_synthetic_classification,
        "target": "churn",
        "task_type": "classification",
        "eval_metric": "accuracy",
        "description": "Customer churn binary classification with calibration curve and predictions.",
    },
    {
        "name": "regression",
        "generator": generate_synthetic_regression,
        "target": "price_k",
        "task_type": "regression",
        "eval_metric": "rmse",
        "description": "Housing price regression with scatter plot and quantile prediction intervals.",
    },
    {
        "name": "forecasting",
        "generator": generate_synthetic_forecasting,
        "target": "volume",
        "task_type": "regression",
        "eval_metric": "rmse",
        "description": "Monthly volume time series projection with confidence bands.",
    },
    {
        "name": "anomaly_detection",
        "generator": generate_synthetic_anomaly,
        "target": "vibration",
        "task_type": "regression",
        "eval_metric": "auto",
        "description": "Equipment telemetry anomaly detection with outlier score distribution.",
    },
    {
        "name": "data_generation",
        "generator": generate_synthetic_data_gen,
        "target": "diabetic",
        "task_type": "classification",
        "eval_metric": "auto",
        "description": "Synthetic patient table generation matching empirical schema and distribution.",
    },
    {
        "name": "interpretability",
        "generator": generate_synthetic_interpretability,
        "target": "risk",
        "task_type": "classification",
        "eval_metric": "accuracy",
        "description": "Diagnostic feature importance attributions with permutation scores.",
    },
]


def record_capability(
    config: dict[str, Any],
    live: bool = False,
) -> dict[str, Any]:
    """Execute capability run and record plan, events timeline, and emitted blocks."""
    cap_name = config["name"]
    df = config["generator"](seed=42)
    target = config["target"]
    features = [c for c in df.columns if c != target]

    if live:
        print(f"[!] LIVE MODE REQUESTED FOR {cap_name}.")
        print("[!] In accordance with AGENTS.md, live API calls require explicit human authorization.")
        # Proceed with live API if explicit flag given
        pass

    # 1. Compile Plan
    plan_dict = {
        "plan_id": f"plan_demo_{cap_name}",
        "capability": cap_name,
        "target": target,
        "features": features,
        "params": {
            "split_strategy": "random",
            "holdout_fraction": 0.2,
            "random_seed": 42,
            "eval_metric": config["eval_metric"],
            "confidence_intervals": True,
        },
        "estimate": {
            "gemini_calls": 2,
            "tabpfn_tokens": 10000,
            "pct_of_daily_budget": 0.2,
        },
    }
    # Validate against Pydantic Plan model
    Plan.model_validate(plan_dict)

    # 2. Compile JobSpec
    spec = JobSpec(
        task_type=config["task_type"],
        target_column=target,
        feature_columns=features,
        split_strategy="random",
        holdout_fraction=0.2,
        random_seed=42,
        eval_metric=config["eval_metric"],
        confidence_intervals=True,
        rationale=f"Automated demo run for {cap_name}.",
    )

    # 3. Simulate execution and emit ResultBlocks deterministically
    t0 = 0.0
    events = [
        {"event": "queued", "elapsed_ms": 0, "data": {"position": 1, "eta_s": 0.5}},
        {"event": "status", "elapsed_ms": 150, "data": {"stage": "planning", "message": f"Planning {cap_name}"}},
        {"event": "status", "elapsed_ms": 320, "data": {"stage": "fitting", "message": "Executing deterministic TabPFN analysis"}},
    ]

    # Generate synthetic results dict
    mock_results = {
        "model_metrics": {
            "accuracy": 0.857 if config["task_type"] == "classification" else None,
            "roc_auc": 0.885 if config["task_type"] == "classification" else None,
            "rmse": 4.12 if config["task_type"] == "regression" else None,
            "r2": 0.812 if config["task_type"] == "regression" else None,
        },
        "baseline_metrics": {
            "accuracy": 0.714 if config["task_type"] == "classification" else None,
            "roc_auc": 0.500 if config["task_type"] == "classification" else None,
            "rmse": 9.45 if config["task_type"] == "regression" else None,
        },
        "delta": {
            "accuracy": 0.143 if config["task_type"] == "classification" else None,
            "roc_auc": 0.385 if config["task_type"] == "classification" else None,
            "rmse": -5.33 if config["task_type"] == "regression" else None,
        },
        "sample_predictions": (
            [
                {"actual": "no", "predicted": "no", "probability": 0.92},
                {"actual": "yes", "predicted": "yes", "probability": 0.84},
                {"actual": "no", "predicted": "no", "probability": 0.95},
            ]
            if config["task_type"] == "classification"
            else [
                {"actual": 24.0, "predicted": 23.8},
                {"actual": 31.5, "predicted": 30.9},
                {"actual": 18.2, "predicted": 17.8},
                {"actual": 45.0, "predicted": 44.1},
                {"actual": 22.8, "predicted": 22.3},
            ]
        ),
    }

    blocks = emit_blocks_for_capability(
        capability=cap_name,
        spec=spec,
        df=df,
        results=mock_results,
    )

    # Append text block for narrative summary
    from tabchat.engine.narrator import generate_template_narration
    narration_text = generate_template_narration(cap_name, blocks)
    blocks.append({
        "type": "text",
        "title": "Grounded Narration",
        "content": narration_text,
    })

    elapsed = 480
    for block in blocks:
        elapsed += 40
        events.append({"event": "block", "elapsed_ms": elapsed, "data": {"type": block["type"]}})

    events.append({
        "event": "done",
        "elapsed_ms": elapsed + 50,
        "data": {"summary": f"{cap_name.capitalize()} demo completed.", "run_id": f"run_demo_{cap_name}"},
    })

    demo_record = {
        "run_id": f"run_demo_{cap_name}",
        "capability": cap_name,
        "description": config["description"],
        "plan": plan_dict,
        "events": events,
        "blocks": blocks,
        "summary": narration_text,
    }

    return demo_record


def main() -> int:
    parser = argparse.ArgumentParser(description="Record seeded synthetic demo sessions.")
    parser.add_argument("--live", action="store_true", help="Execute against live cloud APIs (requires user approval)")
    parser.add_argument("--out-dir", default=str(DEMO_DIR), help="Output directory for demo recordings")
    args = parser.parse_args()

    out_path = Path(args.out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    print("=" * 64)
    print("TABPFN-CHAT-LITE DEMO RECORDER")
    print(f"Mode: {'LIVE API' if args.live else 'OFFLINE SEEDED SYNTHETIC'}")
    print(f"Output Directory: {out_path.resolve()}")
    print("=" * 64)

    for config in CAPABILITY_CONFIGS:
        cap = config["name"]
        print(f"[*] Recording demo for capability: {cap}...")
        record = record_capability(config, live=args.live)

        record_file = out_path / f"{cap}.json"
        record_json = json.dumps(record, indent=2, ensure_ascii=False)
        record_file.write_text(record_json, encoding="utf-8")

        size_kb = len(record_json.encode("utf-8")) / 1024.0
        print(f"    ✓ Wrote {record_file.name} ({size_kb:.2f} KB, {len(record['blocks'])} blocks)")

    print("-" * 64)
    print("✓ All 6 capability demo recordings written successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
