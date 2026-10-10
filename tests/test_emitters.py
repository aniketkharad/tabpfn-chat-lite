"""Test suite for deterministic ResultBlock emitters across all 6 capabilities.

Verifies:
1. Every capability emits valid contract-conforming ResultBlocks.
2. Every table conforms strictly to contract/schemas/table.json.
3. Every block validates against contract/schemas/result_block.json.
4. Data generation table matches original column order, types, and precision, and is labeled synthetic.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from contract.check import SchemaValidator
from tabchat.engine.emitters import (
    emit_anomaly_detection_blocks,
    emit_blocks_for_capability,
    emit_classification_blocks,
    emit_data_generation_blocks,
    emit_forecasting_blocks,
    emit_interpretability_blocks,
    emit_regression_blocks,
)
from tabchat.schemas.job_spec import JobSpec

SCHEMAS_DIR = Path("contract/schemas")
validator = SchemaValidator(SCHEMAS_DIR)
BLOCK_SCHEMA = json.loads((SCHEMAS_DIR / "result_block.json").read_text(encoding="utf-8"))
TABLE_SCHEMA = json.loads((SCHEMAS_DIR / "table.json").read_text(encoding="utf-8"))


def _validate_all_blocks(blocks: list[dict]):
    """Helper to validate every block in a list against result_block.json and table.json."""
    assert len(blocks) >= 4, f"Expected at least 4 blocks, got {len(blocks)}"
    for idx, block in enumerate(blocks):
        try:
            validator.validate(block, BLOCK_SCHEMA)
        except Exception as exc:
            pytest.fail(f"Block #{idx} ({block.get('type')}) failed schema validation: {exc}")

        if block.get("type") == "table":
            try:
                validator.validate(block["table"], TABLE_SCHEMA)
            except Exception as exc:
                pytest.fail(f"Table in block #{idx} failed table.json validation: {exc}")


# =============================================================================
# 1. Classification Tests
# =============================================================================

def test_emit_classification_blocks():
    """Classification emitter must emit metrics vs baseline, calibration curve, predictions table, and download."""
    spec = JobSpec(
        task_type="classification",
        target_column="churn",
        feature_columns=["age", "tenure", "balance"],
        rationale="Classification demo.",
    )
    df = pd.DataFrame({
        "age": [25, 40, 30, 50, 60],
        "tenure": [1, 5, 3, 8, 10],
        "balance": [1000.0, 5000.0, 2500.0, 12000.0, 8000.0],
        "churn": ["no", "yes", "no", "yes", "no"],
    })
    results = {
        "model_metrics": {"accuracy": 0.857, "roc_auc": 0.885},
        "baseline_metrics": {"accuracy": 0.714, "roc_auc": 0.500},
        "delta": {"accuracy": 0.143, "roc_auc": 0.385},
        "sample_predictions": [
            {"actual": "no", "predicted": "no", "probability": 0.92},
            {"actual": "yes", "predicted": "yes", "probability": 0.84},
        ],
    }

    blocks = emit_classification_blocks(spec, df, results)
    _validate_all_blocks(blocks)

    block_types = [b["type"] for b in blocks]
    assert "metric" in block_types
    assert "chart" in block_types
    assert "table" in block_types
    assert "download" in block_types

    # Specific requirements
    metric_block = next(b for b in blocks if b["type"] == "metric" and b["name"] == "Accuracy")
    assert metric_block["value"] == 0.857
    assert metric_block["baseline_value"] == 0.714
    assert metric_block["delta"] == 0.143

    calib_chart = next(b for b in blocks if b["type"] == "chart" and b["kind"] == "reliability")
    assert "bins" in calib_chart["data"]
    assert "observed_frequencies" in calib_chart["data"]

    pred_table = next(b for b in blocks if b["type"] == "table")
    assert pred_table["table"]["cols"] == ["row_index", "actual_class", "predicted_class", "probability"]


# =============================================================================
# 2. Regression Tests
# =============================================================================

def test_emit_regression_blocks():
    """Regression emitter must emit metrics, scatter chart, interval chart, predictions table, and download."""
    spec = JobSpec(
        task_type="regression",
        target_column="price",
        feature_columns=["sqft", "bedrooms"],
        rationale="Regression demo.",
    )
    df = pd.DataFrame({
        "sqft": [1000, 1500, 2000, 2500],
        "bedrooms": [2, 3, 3, 4],
        "price": [200.0, 310.0, 420.0, 550.0],
    })
    results = {
        "model_metrics": {"rmse": 4.12, "r2": 0.812},
        "baseline_metrics": {"rmse": 9.45},
        "delta": {"rmse": -5.33},
        "sample_predictions": [
            {"actual": 200.0, "predicted": 202.1},
            {"actual": 310.0, "predicted": 308.5},
        ],
    }

    blocks = emit_regression_blocks(spec, df, results)
    _validate_all_blocks(blocks)

    rmse_metric = next(b for b in blocks if b["type"] == "metric" and b["name"] == "RMSE")
    assert rmse_metric["value"] == 4.12
    assert rmse_metric["baseline_value"] == 9.45

    scatter_chart = next(b for b in blocks if b["type"] == "chart" and b["kind"] == "scatter")
    assert "actual" in scatter_chart["data"]
    assert "predicted" in scatter_chart["data"]

    interval_chart = next(b for b in blocks if b["type"] == "chart" and b["kind"] == "interval")
    assert "q10" in interval_chart["data"]
    assert "q90" in interval_chart["data"]


# =============================================================================
# 3. Forecasting Tests
# =============================================================================

def test_emit_forecasting_blocks():
    """Forecasting emitter must emit metrics, line chart with intervals, forecast table, and download."""
    spec = JobSpec(
        task_type="regression",
        target_column="passengers",
        feature_columns=["period"],
        rationale="Forecasting demo.",
    )
    df = pd.DataFrame({
        "period": ["1959-01", "1959-02", "1959-03"],
        "passengers": [360, 380, 400],
    })
    blocks = emit_forecasting_blocks(spec, df, {})
    _validate_all_blocks(blocks)

    line_chart = next(b for b in blocks if b["type"] == "chart" and b["kind"] == "line")
    assert "forecast" in line_chart["data"]
    assert "lower_80" in line_chart["data"]
    assert "upper_80" in line_chart["data"]

    forecast_table = next(b for b in blocks if b["type"] == "table")
    assert "forecast_mean" in forecast_table["table"]["cols"]


# =============================================================================
# 4. Anomaly Detection Tests
# =============================================================================

def test_emit_anomaly_detection_blocks():
    """Anomaly detection emitter must emit metrics, score bars, flagged-rows table, and download."""
    spec = JobSpec(
        task_type="regression",
        target_column="vibration",
        feature_columns=["temp"],
        rationale="Anomaly detection demo.",
    )
    df = pd.DataFrame({
        "vibration": [2.1, 2.3, 8.45, 2.2, 9.72],
        "temp": [70.1, 71.2, 112.4, 69.8, 118.1],
    })
    blocks = emit_anomaly_detection_blocks(spec, df, {})
    _validate_all_blocks(blocks)

    bar_chart = next(b for b in blocks if b["type"] == "chart" and b["kind"] == "bar")
    assert "categories" in bar_chart["data"]
    assert "scores" in bar_chart["data"]

    flagged_table = next(b for b in blocks if b["type"] == "table")
    assert "outlier_score" in flagged_table["table"]["cols"]


# =============================================================================
# 5. Data Generation Tests
# =============================================================================

def test_emit_data_generation_blocks():
    """Data generation emitter must emit table formatted exactly like original, distribution chart, and synthetic label."""
    spec = JobSpec(
        task_type="classification",
        target_column="diabetic",
        feature_columns=["patient_id", "age", "bmi"],
        random_seed=42,
        rationale="Data generation demo.",
    )
    original_df = pd.DataFrame({
        "patient_id": ["P01", "P02", "P03", "P04", "P05"],
        "age": [25, 45, 60, 35, 52],
        "bmi": [21.5, 28.4, 32.1, 24.0, 29.8],
        "diabetic": [False, False, True, False, True],
    })

    blocks = emit_data_generation_blocks(spec, original_df, {})
    _validate_all_blocks(blocks)

    # 1. Verify synthetic table formatting matches original column order and types
    syn_table_block = next(b for b in blocks if b["type"] == "table")
    assert "synthetic" in syn_table_block["title"].lower() or "synthetic" in syn_table_block["description"].lower()
    assert syn_table_block["table"]["cols"] == list(original_df.columns)
    assert syn_table_block["table"]["types"] == ["string", "int", "float", "boolean"]
    assert len(syn_table_block["table"]["rows"]) > 0

    # 2. Verify distribution comparison chart
    dist_chart = next(b for b in blocks if b["type"] == "chart" and b["kind"] == "bar")
    assert "real_percentages" in dist_chart["data"]
    assert "synthetic_percentages" in dist_chart["data"]

    # 3. Verify label that it is synthetic in download filename and description
    download_block = next(b for b in blocks if b["type"] == "download")
    assert "synthetic" in download_block["filename"].lower()
    assert "synthetic" in download_block["description"].lower()


# =============================================================================
# 6. Interpretability Tests
# =============================================================================

def test_emit_interpretability_blocks():
    """Interpretability emitter must emit metrics, importance bars, importance table, and download."""
    spec = JobSpec(
        task_type="classification",
        target_column="risk",
        feature_columns=["glucose", "insulin", "bmi", "age"],
        rationale="Interpretability demo.",
    )
    df = pd.DataFrame({
        "glucose": [90, 150, 180],
        "insulin": [20, 80, 140],
        "bmi": [22.0, 31.0, 35.0],
        "age": [30, 45, 60],
        "risk": [0, 1, 1],
    })
    blocks = emit_interpretability_blocks(spec, df, {})
    _validate_all_blocks(blocks)

    imp_chart = next(b for b in blocks if b["type"] == "chart" and b["kind"] == "importance")
    assert "features" in imp_chart["data"]
    assert "scores" in imp_chart["data"]

    imp_table = next(b for b in blocks if b["type"] == "table")
    assert "feature" in imp_table["table"]["cols"]
    assert "roc_auc_drop" in imp_table["table"]["cols"]


# =============================================================================
# 7. Unified Dispatcher Test
# =============================================================================

@pytest.mark.parametrize("capability", [
    "classification",
    "regression",
    "forecasting",
    "anomaly_detection",
    "data_generation",
    "interpretability",
])
def test_emit_blocks_for_all_capabilities(capability: str):
    """emit_blocks_for_capability dispatcher must emit valid contract blocks for all 6 capabilities."""
    spec = JobSpec(
        task_type="regression" if capability in ("regression", "forecasting") else "classification",
        target_column="target",
        feature_columns=["f1", "f2"],
        rationale="Test dispatcher.",
    )
    df = pd.DataFrame({
        "f1": [1.0, 2.0, 3.0, 4.0],
        "f2": [10, 20, 30, 40],
        "target": [0, 1, 0, 1] if spec.task_type == "classification" else [10.5, 20.2, 30.1, 40.8],
    })
    blocks = emit_blocks_for_capability(capability, spec, df, {})
    _validate_all_blocks(blocks)
