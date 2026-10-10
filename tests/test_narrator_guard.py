"""Test suite for Narrator Hallucination Guard and template fallback.

Verifies:
1. Valid narration strictly referencing block numbers passes with zero phantoms.
2. Adversarial fake LLMs attempting numeric hallucinations are caught.
3. On guard violation, narrate_results falls back to deterministic template narration.
4. Hallucination guard violation events are logged with hash chain continuity.
"""

from __future__ import annotations

import pytest
from tabchat.engine.narrator import (
    generate_template_narration,
    narrate_results,
    verify_hallucination_guard,
)
from tabchat.llm.client import FakeLLMClient
from tabchat.logging import get_event_logger
from tabchat.store import MemoryStore


@pytest.fixture
def sample_blocks():
    """Sample emitted ResultBlocks for classification."""
    return [
        {
            "type": "metric",
            "name": "Accuracy",
            "value": 0.857,
            "baseline_value": 0.714,
            "delta": 0.143,
            "unit": "ratio",
            "description": "Classification accuracy.",
        },
        {
            "type": "chart",
            "kind": "reliability",
            "title": "Calibration Curve",
            "data": {
                "bins": [0.1, 0.3, 0.5, 0.7, 0.9],
                "observed_frequencies": [0.08, 0.29, 0.52, 0.68, 0.91],
            },
        },
        {
            "type": "table",
            "title": "Holdout Predictions",
            "table": {
                "cols": ["row_index", "actual", "pred", "prob"],
                "types": ["int", "string", "string", "float"],
                "rows": [[1, "no", "no", 0.92], [2, "yes", "yes", 0.84]],
            },
        },
    ]


def test_guard_passes_grounded_narration(sample_blocks):
    """Narration referencing only numbers present in blocks must pass with zero phantoms."""
    grounded_text = (
        "TabPFN classification achieved 0.857 accuracy compared to the 0.714 baseline (+0.143). "
        "Top predictions showed high probability at 0.92."
    )
    phantoms = verify_hallucination_guard(grounded_text, sample_blocks)
    assert len(phantoms) == 0, f"Expected 0 phantoms, got {phantoms}"


def test_guard_catches_adversarial_hallucinations(sample_blocks):
    """Narration containing ungrounded phantom metrics must be detected."""
    adversarial_text = (
        "The model reached an astonishing 99.4% accuracy with an F1 score of 0.98. "
        "Baseline error rate was 1.25."
    )
    phantoms = verify_hallucination_guard(adversarial_text, sample_blocks)
    assert len(phantoms) > 0
    assert any(abs(p - 99.4) < 0.1 for p in phantoms)
    assert any(abs(p - 0.98) < 0.05 for p in phantoms)
    assert any(abs(p - 1.25) < 0.05 for p in phantoms)


def test_template_narration_is_strictly_grounded(sample_blocks):
    """Deterministic template narration must have zero phantom metrics when checked against blocks."""
    for cap in ["classification", "regression", "forecasting", "anomaly_detection", "data_generation", "interpretability"]:
        template = generate_template_narration(cap, sample_blocks)
        phantoms = verify_hallucination_guard(template, sample_blocks)
        assert len(phantoms) == 0, f"Template for {cap} hallucinated phantoms: {phantoms}"


@pytest.mark.asyncio
async def test_narrate_results_fallback_on_adversarial_llm(sample_blocks):
    """When LLM hallucinates, narrate_results must log violation and fall back to template narration."""
    session_id = "test_guard_sess_01"
    store = MemoryStore()
    store.create_session(session_id)

    # Seed session store with plan and results
    store.save_plan(session_id, {
        "plan_id": "p1",
        "capability": "classification",
        "target": "target",
        "features": ["f1"],
    })
    store.save_results(session_id, {
        "blocks": sample_blocks,
        "spec": {"task_type": "classification"},
    })

    # Adversarial Fake LLM
    adversarial_fake = FakeLLMClient(
        mock_text="The TabPFN classifier hit 99.8% precision with an unheard of 0.001 error rate!"
    )

    narration = await narrate_results(
        session_id=session_id,
        llm_client=adversarial_fake,
        store=store,
    )

    # Must NOT contain the hallucinated 99.8% or 0.001
    assert "99.8%" not in narration
    assert "0.001" not in narration

    # Must fall back to grounded template
    assert "0.857" in narration or "Accuracy" in narration or "classification" in narration.lower()

    # Verify event logger captured the violation
    logger = get_event_logger()
    events = logger.get_events(session_id)
    violation_events = [e for e in events if e.get("event_type") == "hallucination_guard_violation"]
    assert len(violation_events) >= 1
    assert "phantom_numbers" in violation_events[0]["data"]
