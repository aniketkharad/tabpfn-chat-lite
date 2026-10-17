"""Prior Labs TabPFN direct REST client, offline mock client, and disk cache."""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path
from typing import Any
import httpx
import numpy as np
import pandas as pd

from tabchat.config import get_settings

logger = logging.getLogger("tabchat.tabpfn")


class TabPFNError(Exception):
    """Base exception for TabPFN execution failures."""


class TabPFNRateLimitError(TabPFNError):
    """Raised when TabPFN API quota or rate limits are exceeded (HTTP 429)."""


def _sanitize_for_cache(obj: Any) -> Any:
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return str(obj)


class DiskFitCache:
    """Manages disk-backed caching of TabPFN model executions under data/cache/tabpfn/."""

    def __init__(self, cache_dir: Path | str | None = None) -> None:
        if cache_dir is None:
            self.cache_dir = get_settings().DATA_DIR / "cache" / "tabpfn"
        else:
            self.cache_dir = Path(cache_dir).resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, dataset_hash: str, spec_hash: str) -> Path:
        filename = f"{dataset_hash}_{spec_hash}.json"
        return self.cache_dir / filename

    def get(self, dataset_hash: str, spec_hash: str) -> dict[str, Any] | None:
        """Retrieve cached execution results if available, else None."""
        c_path = self._cache_path(dataset_hash, spec_hash)
        if c_path.exists():
            try:
                data = json.loads(c_path.read_text(encoding="utf-8"))
                logger.info("TabPFN Cache Hit: %s", c_path.name)
                return data
            except Exception as e:
                logger.warning("Corrupted cache file %s, discarding: %e", c_path.name, e)
                c_path.unlink(missing_ok=True)
                return None
        return None

    def set(self, dataset_hash: str, spec_hash: str, results: dict[str, Any]) -> None:
        """Persist execution results under the canonical hash key."""
        c_path = self._cache_path(dataset_hash, spec_hash)
        c_path.write_text(
            json.dumps(results, indent=2, ensure_ascii=False, default=_sanitize_for_cache),
            encoding="utf-8",
        )
        logger.info("TabPFN Cache Stored: %s", c_path.name)


class TabPFNClient:
    """Production asynchronous TabPFN client invoking Prior Labs REST API."""

    BASE_URL = "https://api.priorlabs.ai"

    def __init__(self, token: str | None = None, timeout_seconds: float = 90.0) -> None:
        settings = get_settings()
        self.token = token or settings.TABPFN_TOKEN
        self.timeout = timeout_seconds or float(settings.TABPFN_FIT_TIMEOUT_SECONDS)
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def fit_and_predict(
        self,
        train_df: pd.DataFrame,
        test_df: pd.DataFrame,
        target_col: str,
        task: str,  # "classification" or "regression"
    ) -> dict[str, Any]:
        """Execute full fit and predict pipeline against Prior Labs REST API."""
        X_train = train_df.drop(columns=[target_col])
        y_train = train_df[target_col]
        X_test = test_df.drop(columns=[target_col]) if target_col in test_df.columns else test_df
        return await self.fit_and_predict_partitions(task, X_train, y_train, X_test)

    async def fit_and_predict_partitions(
        self,
        task_type: str,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_holdout: pd.DataFrame,
        random_seed: int = 42,
    ) -> dict[str, Any]:
        """Execute full fit and predict pipeline against Prior Labs REST API using separate partitions."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            X_train_csv = X_train.to_csv(index=False).encode("utf-8")
            y_name = str(y_train.name) if y_train.name else "target"
            y_train_csv = y_train.to_frame(name=y_name).to_csv(index=False).encode("utf-8")
            X_holdout_csv = X_holdout.to_csv(index=False).encode("utf-8")

            # 1. Prepare train set upload
            prep_payload = {
                "x_train_info": {"format": "csv"},
                "y_train_info": {"format": "csv"},
            }
            prep_train_resp = await client.post(
                f"{self.BASE_URL}/tabpfn/prepare_train_set_upload",
                headers=self.headers,
                json=prep_payload,
            )
            if prep_train_resp.status_code == 429:
                raise TabPFNRateLimitError(f"TabPFN quota exceeded: {prep_train_resp.text}")
            prep_train_resp.raise_for_status()
            prep_train_data = prep_train_resp.json()
            train_upload_id = prep_train_data["train_set_upload_id"]
            x_train_info = prep_train_data["x_train_info"]
            y_train_info = prep_train_data["y_train_info"]

            # 2. Upload train features and targets
            x_headers = dict(x_train_info.get("required_headers", {}))
            if "Content-Type" not in x_headers and "content-type" not in x_headers:
                x_headers["Content-Type"] = "text/csv"
            put_x = await client.put(
                x_train_info["signed_urls"][0],
                content=X_train_csv,
                headers=x_headers,
            )
            put_x.raise_for_status()

            y_headers = dict(y_train_info.get("required_headers", {}))
            if "Content-Type" not in y_headers and "content-type" not in y_headers:
                y_headers["Content-Type"] = "text/csv"
            put_y = await client.put(
                y_train_info["signed_urls"][0],
                content=y_train_csv,
                headers=y_headers,
            )
            put_y.raise_for_status()

            # 3. Fit model
            fit_payload = {
                "train_set_upload_id": train_upload_id,
                "task_config": {
                    "task": task_type,
                    "tabpfn_config": {"model_path": "v3.5_default"},
                },
            }
            fit_resp = await client.post(
                f"{self.BASE_URL}/tabpfn/fit",
                headers=self.headers,
                json=fit_payload,
            )
            if fit_resp.status_code == 429:
                raise TabPFNRateLimitError(f"TabPFN quota exceeded: {fit_resp.text}")
            fit_resp.raise_for_status()
            fitted_data = fit_resp.json()
            fitted_train_set_id = fitted_data["fitted_train_set_id"]

            # 4. Prepare test set upload
            prep_test_payload = {
                "fitted_train_set_id": fitted_train_set_id,
                "x_test_info": {"format": "csv"},
            }
            prep_test_resp = await client.post(
                f"{self.BASE_URL}/tabpfn/prepare_test_set_upload",
                headers=self.headers,
                json=prep_test_payload,
            )
            if prep_test_resp.status_code == 429:
                raise TabPFNRateLimitError(f"TabPFN quota exceeded: {prep_test_resp.text}")
            prep_test_resp.raise_for_status()
            prep_test_data = prep_test_resp.json()
            test_upload_id = prep_test_data["test_set_upload_id"]
            x_test_info = prep_test_data["x_test_info"]

            # 5. Upload test CSV bytes
            test_headers = dict(x_test_info.get("required_headers", {}))
            if "Content-Type" not in test_headers and "content-type" not in test_headers:
                test_headers["Content-Type"] = "text/csv"
            put_test = await client.put(
                x_test_info["signed_urls"][0],
                content=X_holdout_csv,
                headers=test_headers,
            )
            put_test.raise_for_status()

            # 6. Predict
            if task_type == "regression":
                predict_params = {"output_type": "quantiles", "quantiles": [0.1, 0.5, 0.9]}
            else:
                predict_params = {"output_type": "probas"}

            predict_payload: dict[str, Any] = {
                "fitted_train_set_id": fitted_train_set_id,
                "test_set_upload_id": test_upload_id,
                "task_config": {
                    "task": task_type,
                    "tabpfn_config": {"model_path": "v3.5_default"},
                    "predict_params": predict_params,
                },
            }

            pred_resp = await client.post(
                f"{self.BASE_URL}/tabpfn/predict",
                headers=self.headers,
                json=predict_payload,
            )
            if pred_resp.status_code == 429:
                raise TabPFNRateLimitError(f"TabPFN quota exceeded: {pred_resp.text}")
            pred_resp.raise_for_status()
            pred_data = pred_resp.json()

            # 7. Post-process response into standard format
            if task_type == "classification":
                raw_prediction = pred_data.get("prediction", [])
                metadata = pred_data.get("metadata", {})
                classes = metadata.get("classes")
                if not classes:
                    classes = list(pd.Series(y_train.dropna().unique()).sort_values())

                probas = np.asarray(raw_prediction, dtype=float)
                if probas.ndim == 1:
                    probas = np.column_stack([1.0 - probas, probas])
                row_sums = np.sum(probas, axis=1, keepdims=True)
                row_sums[row_sums == 0] = 1.0
                probas = probas / row_sums

                pred_indices = np.argmax(probas, axis=1)
                predictions = [classes[idx] for idx in pred_indices]
                return {
                    "task": "classification",
                    "predictions": predictions,
                    "probabilities": probas.tolist(),
                    "classes": classes,
                    "model_version": "v3.5_default",
                }
            else:
                raw_pred = pred_data.get("prediction", {})
                if isinstance(raw_pred, dict):
                    q10 = np.asarray(raw_pred.get("0.1", raw_pred.get("q10", [])))
                    q50 = np.asarray(raw_pred.get("0.5", raw_pred.get("q50", [])))
                    q90 = np.asarray(raw_pred.get("0.9", raw_pred.get("q90", [])))
                    preds = q50
                elif isinstance(raw_pred, (list, np.ndarray)):
                    arr = np.asarray(raw_pred, dtype=float)
                    if arr.ndim == 2 and arr.shape[1] >= 3:
                        q10, q50, q90 = arr[:, 0], arr[:, 1], arr[:, 2]
                        preds = q50
                    elif arr.ndim == 1:
                        preds = arr
                        std_val = float(y_train.std()) if len(y_train) > 1 else 1.0
                        q10 = preds - 1.28 * std_val
                        q50 = preds
                        q90 = preds + 1.28 * std_val
                    else:
                        preds = arr.flatten()
                        std_val = float(y_train.std()) if len(y_train) > 1 else 1.0
                        q10 = preds - 1.28 * std_val
                        q50 = preds
                        q90 = preds + 1.28 * std_val
                else:
                    mean_val = float(y_train.mean())
                    std_val = float(y_train.std()) if len(y_train) > 1 else 1.0
                    preds = np.full(len(X_holdout), mean_val)
                    q10 = preds - 1.28 * std_val
                    q50 = preds
                    q90 = preds + 1.28 * std_val

                return {
                    "task": "regression",
                    "predictions": preds.tolist() if isinstance(preds, np.ndarray) else preds,
                    "quantiles": {
                        "q10": q10.tolist() if isinstance(q10, np.ndarray) else q10,
                        "q50": q50.tolist() if isinstance(q50, np.ndarray) else q50,
                        "q90": q90.tolist() if isinstance(q90, np.ndarray) else q90,
                    },
                    "model_version": "v3.5_default",
                }


class FakeTabPFNClient:
    """Deterministic offline mock TabPFN client for testing without external API calls."""

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self.call_count = 0

    async def fit_and_predict(
        self,
        train_df: pd.DataFrame,
        test_df: pd.DataFrame,
        target_col: str,
        task: str,
    ) -> dict[str, Any]:
        """Simulate realistic predictions based on training data distribution and features."""
        X_train = train_df.drop(columns=[target_col])
        y_train = train_df[target_col]
        X_test = test_df.drop(columns=[target_col]) if target_col in test_df.columns else test_df
        return await self.fit_and_predict_partitions(task, X_train, y_train, X_test, random_seed=self.seed)

    async def fit_and_predict_partitions(
        self,
        task_type: str,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_holdout: pd.DataFrame,
        random_seed: int = 42,
    ) -> dict[str, Any]:
        """Simulate realistic predictions based on training data partitions and features."""
        self.call_count += 1
        rng = np.random.RandomState(random_seed or (self.seed + self.call_count))
        n_test = len(X_holdout)

        if task_type == "classification":
            y_arr = y_train.to_numpy()
            classes = list(pd.Series(y_arr).dropna().unique())
            try:
                classes = sorted(classes)
            except Exception:
                pass
            n_classes = len(classes)

            raw_scores = rng.normal(loc=0.0, scale=1.0, size=(n_test, n_classes))
            exp_scores = np.exp(raw_scores - np.max(raw_scores, axis=1, keepdims=True))
            probs = exp_scores / np.sum(exp_scores, axis=1, keepdims=True)

            predicted_indices = np.argmax(probs, axis=1)
            predicted_classes = [
                int(classes[idx]) if isinstance(classes[idx], (np.integer, int))
                else float(classes[idx]) if isinstance(classes[idx], (np.floating, float))
                else str(classes[idx])
                for idx in predicted_indices
            ]

            return {
                "task": "classification",
                "classes": [str(c) for c in classes],
                "predictions": predicted_classes,
                "probabilities": probs.tolist(),
                "model_version": "fake-tabpfn-3.5",
            }

        else:  # regression
            y_arr = y_train.to_numpy(dtype=float)
            mean_y = float(np.mean(y_arr))
            std_y = float(np.std(y_arr)) if len(y_arr) > 1 else 1.0

            point_preds = mean_y + rng.normal(0.0, 0.3 * std_y, size=n_test)
            q10 = point_preds - 1.28 * (0.3 * std_y)
            q50 = point_preds
            q90 = point_preds + 1.28 * (0.3 * std_y)

            return {
                "task": "regression",
                "predictions": point_preds.tolist(),
                "quantiles": {
                    "q10": q10.tolist(),
                    "q50": q50.tolist(),
                    "q90": q90.tolist(),
                },
                "model_version": "fake-tabpfn-3.5",
            }
