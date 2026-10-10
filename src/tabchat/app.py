"""FastAPI application factory and instance for tabchat."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from tabchat.middleware.auth import GatewayHMACMiddleware
from tabchat.routes.api import internal_router, router as api_router

FRONTEND_DIR = Path(__file__).parent / "frontend"


def create_app() -> FastAPI:
    """Create and configure the tabchat FastAPI application."""
    app = FastAPI(
        title="tabpfn-chat-lite",
        description="Lightweight public tabular analysis web app with TabPFN and Gemini",
        version="0.1.0",
    )

    # Configure offline fakes if requested via environment
    import os
    if os.environ.get("USE_FAKES") == "1" or os.environ.get("DEMO_MODE") == "1":
        from typing import Any
        from tabchat.engine.planner import PlannerOutput
        from tabchat.llm.client import FakeLLMClient
        from tabchat.schemas.job_spec import JobSpec

        def dynamic_mock_structured(messages: list[dict[str, Any]], schema: Any) -> Any:
            last_msg = str(messages[-1].get("content", "")) if messages else ""
            if "binary" in last_msg.lower() or "churn" in last_msg.lower() or "predict" in last_msg.lower():
                return PlannerOutput(
                    is_clarification=False,
                    clarification_message=None,
                    selected_skills=["task_and_target", "leakage_and_splits"],
                    proposed_spec=JobSpec(
                        task_type="classification",
                        target_column="churn",
                        feature_columns=["age", "tenure", "balance"],
                        eval_metric="accuracy",
                        holdout_fraction=0.2,
                        seed=42,
                        rationale="Predict customer churn based on account features.",
                    ),
                )
            return PlannerOutput(
                is_clarification=True,
                clarification_message="Would you like binary classification with target column churn?",
                selected_skills=["task_and_target"],
                proposed_spec=None,
            )

        def mock_tabpfn_api_caller(
            task_type: str,
            X_train: Any,
            y_train: Any,
            X_holdout: Any,
            random_seed: int = 42,
            **kwargs: Any,
        ) -> dict[str, Any]:
            n_test = len(X_holdout)
            if task_type == "classification":
                preds = [1 if i % 2 == 0 else 0 for i in range(n_test)]
                probs = [[0.8, 0.2] if p == 1 else [0.2, 0.8] for p in preds]
                return {
                    "predictions": preds,
                    "probabilities": probs,
                    "classes": [0, 1],
                    "model_path": "v3.5_default",
                }
            preds = [42.0 + (i * 1.5) for i in range(n_test)]
            return {
                "predictions": preds,
                "quantiles": {"q10": [p - 5.0 for p in preds], "q50": preds, "q90": [p + 5.0 for p in preds]},
                "model_path": "v3.5_default",
            }

        app.state.llm_client = FakeLLMClient(
            mock_text="TabPFN achieved 85% accuracy on churn prediction.",
            mock_structured=dynamic_mock_structured,
        )
        app.state.tabpfn_api_caller = mock_tabpfn_api_caller

    # Gateway HMAC Authentication Middleware
    app.add_middleware(GatewayHMACMiddleware)

    # Allow development origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Readiness probe: /health is open and reveals nothing sensitive
    @app.get("/health")
    async def health_check() -> JSONResponse:
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", ".000Z")
        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "version": "0.1.0",
                "timestamp": now_iso,
            },
        )

    # Mount API routes
    app.include_router(api_router)
    app.include_router(internal_router)

    # Serve static assets and single-page application fallback if present and enabled.
    # In production (or when ENABLE_LEGACY_FRONTEND=0), legacy prototype static files are unmounted.
    enable_legacy = (
        FRONTEND_DIR.exists()
        and os.environ.get("ENABLE_LEGACY_FRONTEND", "1" if not os.environ.get("PRODUCTION") else "0") == "1"
    )
    if enable_legacy:
        app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
        samples_dir = FRONTEND_DIR / "samples"
        if samples_dir.exists():
            app.mount("/samples", StaticFiles(directory=samples_dir), name="samples")

        @app.get("/")
        @app.get("/index.html")
        async def serve_index() -> FileResponse:
            return FileResponse(FRONTEND_DIR / "index.html")

    return app


app = create_app()
