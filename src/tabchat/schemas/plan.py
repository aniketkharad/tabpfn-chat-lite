"""Contract-adherent Plan schema for tabpfn-chat-lite.

Source of truth: contract/schemas/plan.json
Invariants:
- Executor accepts only a Plan that validates against this schema.
- All 6 TabPFN capabilities supported.
"""

from __future__ import annotations

import json
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class PlanEstimate(BaseModel):
    """Resource estimation for proposed plan execution."""

    gemini_calls: int = Field(ge=0, description="Projected Gemini API calls")
    tabpfn_tokens: int = Field(ge=0, description="Projected TabPFN token charge")
    pct_of_daily_budget: float = Field(
        ge=0.0, le=100.0, description="Percentage of daily token budget"
    )


class PlanParams(BaseModel):
    """Parameters tailored to execution capability."""

    split_strategy: Optional[Literal["random", "stratified", "chronological", "group"]] = "random"
    split_column: Optional[str] = None
    holdout_fraction: Optional[float] = Field(default=0.2, ge=0.05, le=0.5)
    random_seed: Optional[int] = 42
    eval_metric: Optional[str] = "auto"
    confidence_intervals: Optional[bool] = True
    forecast_horizon: Optional[int] = Field(default=None, ge=1)
    n_samples: Optional[int] = Field(default=None, ge=1)
    n_permutations: Optional[int] = Field(default=None, ge=1)


class Plan(BaseModel):
    """Validated execution plan compiled by the Planner matching contract/schemas/plan.json."""

    plan_id: str = Field(
        ...,
        pattern=r"^plan_[a-zA-Z0-9_-]+$",
        description="Unique identifier for the planned analysis job",
    )
    capability: Literal[
        "classification",
        "regression",
        "forecasting",
        "anomaly_detection",
        "data_generation",
        "interpretability",
    ] = Field(..., description="TabPFN capability to execute")
    target: Optional[str] = Field(
        default=None,
        description="Target column name, or null for unsupervised tasks",
    )
    features: list[str] = Field(
        default_factory=list,
        description="List of feature columns to include",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Execution parameters tailored to the capability",
    )
    estimate: PlanEstimate = Field(
        ...,
        description="Pre-execution resource and quota cost projection",
    )

    def to_contract_dict(self) -> dict[str, Any]:
        """Return dict strictly compliant with contract/schemas/plan.json."""
        return self.model_dump()

    def canonical_json(self) -> str:
        """Deterministically formatted JSON representation."""
        return json.dumps(self.model_dump(), sort_keys=True, separators=(",", ":"))
