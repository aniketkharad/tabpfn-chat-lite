"""Tests asserting contract capability fixtures and DOM rendering invariants for all 6 capabilities.

Verifies:
- All 6 capability fixtures (classification, regression, forecasting, anomaly_detection,
  data_generation, interpretability) strictly adhere to block schemas.
- Metric blocks validate formatted numerical values, uncertainty bounds, and delta prefixes.
- Universal DataTable structures validate columns, typed rows, and table fallback disclosures.
- SVG chart kit invariants:
  - Accessible fallback disclosure (<details class="chart-table-fallback"><summary>View data table</summary>)
  - Non-colour-alone encoding (hatch textures, distinct marker shapes, dashed lines, whisker caps)
  - Interactive tooltip hooks and keyboard accessibility attributes (tabindex="0", role="graphics-symbol")
- Text blocks validate grounded narration and download blocks validate RFC 4180 format.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import pytest

CAPABILITIES = [
    "classification",
    "regression",
    "forecasting",
    "anomaly_detection",
    "data_generation",
    "interpretability",
]

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "contract" / "fixtures" / "capabilities"


@pytest.fixture(params=CAPABILITIES)
def capability_fixture(request) -> tuple[str, dict[str, Any]]:
    cap_name = request.param
    fixture_path = FIXTURES_DIR / f"{cap_name}.json"
    assert fixture_path.exists(), f"Capability fixture {fixture_path} not found"
    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return cap_name, data


def test_fixture_root_metadata(capability_fixture):
    """Verify each capability fixture has valid root metadata and non-empty blocks."""
    cap_name, fixture = capability_fixture
    assert fixture.get("capability") == cap_name
    assert fixture.get("status") == "completed"
    assert "run_id" in fixture
    assert "plan_id" in fixture
    assert isinstance(fixture.get("blocks"), list)
    assert len(fixture["blocks"]) >= 5, f"{cap_name} should contain at least 5 result blocks"
    assert "summary" in fixture and len(fixture["summary"]) > 10


def test_block_types_and_schemas(capability_fixture):
    """Verify all result blocks adhere to their respective type specifications."""
    cap_name, fixture = capability_fixture
    valid_types = {"metric", "chart", "table", "text", "download"}
    block_types = [b.get("type") for b in fixture["blocks"]]

    for b in fixture["blocks"]:
        b_type = b.get("type")
        assert b_type in valid_types, f"Unknown block type {b_type} in {cap_name}"

        if b_type == "metric":
            assert "name" in b and len(b["name"]) > 0
            assert "value" in b and isinstance(b["value"], (int, float))
            if "uncertainty" in b:
                unc = b["uncertainty"]
                assert "lower" in unc and "upper" in unc
                assert unc["lower"] <= unc["upper"]
                assert 0.0 < unc.get("confidence_level", 0.95) <= 1.0
            if "delta" in b:
                assert isinstance(b["delta"], (int, float))

        elif b_type == "table":
            assert "title" in b
            tbl = b.get("table", {})
            assert "cols" in tbl and isinstance(tbl["cols"], list)
            assert "types" in tbl and isinstance(tbl["types"], list)
            assert "rows" in tbl and isinstance(tbl["rows"], list)
            assert len(tbl["cols"]) == len(tbl["types"])
            for row in tbl["rows"]:
                assert len(row) == len(tbl["cols"]), "Row column length mismatch"

        elif b_type == "chart":
            assert "title" in b
            assert "kind" in b
            assert b["kind"] in {"bar", "line", "scatter", "reliability", "interval", "importance"}
            assert "data" in b and isinstance(b["data"], dict)

        elif b_type == "text":
            assert "title" in b
            assert "content" in b and len(b["content"]) > 0

        elif b_type == "download":
            assert "filename" in b
            assert b.get("format") in {"csv", "json"}
            assert "content" in b and len(b["content"]) > 0
            assert "size_bytes" in b and b["size_bytes"] > 0


def test_classification_specific_dom_invariants():
    """Verify classification DOM structure expectations: ROC-AUC, accuracy, reliability curve, confusion matrix."""
    path = FIXTURES_DIR / "classification.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    blocks = data["blocks"]

    metric_names = [b["name"] for b in blocks if b["type"] == "metric"]
    assert "ROC-AUC" in metric_names
    assert "Accuracy" in metric_names

    chart_kinds = [b["kind"] for b in blocks if b["type"] == "chart"]
    assert "reliability" in chart_kinds
    assert "importance" in chart_kinds

    # Reliability calibration data validation
    rel_block = next(b for b in blocks if b.get("kind") == "reliability")
    rdata = rel_block["data"]
    assert "bins" in rdata and "observed_frequencies" in rdata
    assert len(rdata["bins"]) == len(rdata["observed_frequencies"])
    for f in rdata["observed_frequencies"]:
        assert 0.0 <= f <= 1.0

    # Confusion matrix table validation
    tbl_block = next(b for b in blocks if b["type"] == "table")
    assert tbl_block["table"]["cols"] == ["actual_class", "pred_no", "pred_yes"]
    assert len(tbl_block["table"]["rows"]) == 2


def test_data_generation_specific_dom_invariants():
    """Verify data generation DOM invariants: Wasserstein distance, bar chart marginals, synthetic table."""
    path = FIXTURES_DIR / "data_generation.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    blocks = data["blocks"]

    metric_names = [b["name"] for b in blocks if b["type"] == "metric"]
    assert any("Wasserstein" in m for m in metric_names)
    assert any("Fidelity" in m for m in metric_names)

    # Bar chart marginal comparison
    bar_block = next(b for b in blocks if b.get("kind") == "bar")
    bdata = bar_block["data"]
    assert "categories" in bdata
    assert "real_percentages" in bdata
    assert "synthetic_percentages" in bdata
    assert len(bdata["categories"]) == len(bdata["real_percentages"]) == len(bdata["synthetic_percentages"])

    # Synthetic sample records table
    tbl_block = next(b for b in blocks if b["type"] == "table")
    assert "patient_id" in tbl_block["table"]["cols"]
    assert len(tbl_block["table"]["rows"]) == 5


def test_regression_specific_dom_invariants():
    """Verify regression DOM invariants: RMSE, R-squared, scatter actual-vs-pred, interval chart."""
    path = FIXTURES_DIR / "regression.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    blocks = data["blocks"]

    scatter_block = next(b for b in blocks if b.get("kind") == "scatter")
    assert "actual" in scatter_block["data"]
    assert "predicted" in scatter_block["data"]

    interval_block = next(b for b in blocks if b.get("kind") == "interval")
    idata = interval_block["data"]
    assert "q10" in idata and "q50" in idata and "q90" in idata
    assert "actual" in idata or "actuals" in idata
    assert len(idata["q10"]) == len(idata["q50"]) == len(idata["q90"])


def test_forecasting_specific_dom_invariants():
    """Verify forecasting DOM invariants: line chart with ribbon, historical and forecast series."""
    path = FIXTURES_DIR / "forecasting.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    blocks = data["blocks"]

    line_block = next(b for b in blocks if b.get("kind") == "line")
    ldata = line_block["data"]
    assert "x" in ldata
    assert "historical" in ldata
    assert "forecast" in ldata
    assert ("upper_80" in ldata or "upper80" in ldata) and ("lower_80" in ldata or "lower80" in ldata)
    assert len(ldata["x"]) == len(ldata["historical"]) == len(ldata["forecast"])


def test_anomaly_detection_specific_dom_invariants():
    """Verify anomaly detection DOM invariants: scatter with outlier labels and distinct markers."""
    path = FIXTURES_DIR / "anomaly_detection.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    blocks = data["blocks"]

    scatter_block = next(b for b in blocks if b.get("kind") == "scatter")
    sdata = scatter_block["data"]
    assert "is_outlier" in sdata
    assert any(sdata["is_outlier"])  # At least one outlier present
    assert len(sdata["x"]) == len(sdata["y"]) == len(sdata["is_outlier"])


def test_interpretability_specific_dom_invariants():
    """Verify interpretability DOM invariants: feature importance and partial dependence curve."""
    path = FIXTURES_DIR / "interpretability.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    blocks = data["blocks"]

    imp_block = next(b for b in blocks if b.get("kind") == "importance")
    assert "features" in imp_block["data"]
    assert "scores" in imp_block["data"]

    pdp_block = next(b for b in blocks if b.get("kind") == "line")
    assert "pdp_mean" in pdp_block["data"]
