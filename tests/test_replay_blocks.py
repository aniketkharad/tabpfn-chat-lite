import json
from pathlib import Path
import sys
import pandas as pd
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from contract.check import SchemaValidator
from tabchat.engine.executor import execute_plan
from tabchat.replay import replay_run_blocks, replay_run_sse_stream
from tabchat.store import MemoryStore

SCHEMAS_DIR = Path("contract/schemas")
validator = SchemaValidator(SCHEMAS_DIR)
SSE_SCHEMA = json.loads((SCHEMAS_DIR / "sse_event.json").read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_replay_run_blocks_identical():
    """A recorded run must replay to an identical block stream with zero upstream calls."""
    store = MemoryStore()
    session_id = "replay_sess_01"
    store.create_session(session_id)

    # 1. Setup dataset in store
    df = pd.DataFrame({
        "age": [25, 45, 30, 50, 35, 60],
        "balance": [1000.0, 5000.0, 2000.0, 8000.0, 3000.0, 12000.0],
        "churn": ["no", "yes", "no", "yes", "no", "yes"],
    })
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    store.save_dataset(session_id, csv_bytes, {"row_count": len(df), "col_count": len(df.columns)})

    # 2. Setup validated Plan
    plan = {
        "plan_id": "plan_test_replay_01",
        "capability": "classification",
        "target": "churn",
        "features": ["age", "balance"],
        "params": {
            "split_strategy": "random",
            "holdout_fraction": 0.2,
            "random_seed": 42,
            "eval_metric": "accuracy",
            "confidence_intervals": True,
        },
        "estimate": {
            "gemini_calls": 2,
            "tabpfn_tokens": 10000,
            "pct_of_daily_budget": 0.2,
        },
    }
    store.save_plan(session_id, plan)

    # Mock caller for offline execution
    def offline_mock_caller(*args, **kwargs):
        return {
            "predictions": ["no", "yes"],
            "probabilities": [[0.9, 0.1], [0.2, 0.8]],
            "classes": ["no", "yes"],
        }

    # 3. Execute plan
    original_results = await execute_plan(
        session_id=session_id,
        store=store,
        api_caller=offline_mock_caller,
    )
    original_blocks = original_results.get("blocks", [])
    assert len(original_blocks) >= 4

    # 4. Replay blocks with ZERO upstream calls
    replayed_blocks = replay_run_blocks(session_id=session_id, store=store)

    # 5. Assert identity
    assert len(replayed_blocks) == len(original_blocks)
    assert replayed_blocks == original_blocks, "Replayed blocks differed from original run blocks!"

    # 6. Replay SSE stream
    sse_frames = replay_run_sse_stream(session_id=session_id, store=store)
    assert len(sse_frames) >= 6

    # Parse and validate each SSE frame against sse_event.json
    for frame in sse_frames:
        lines = frame.strip().split("\n")
        frame_dict = {}
        for line in lines:
            if line.startswith("id: "):
                frame_dict["id"] = line[4:].strip()
            elif line.startswith("event: "):
                frame_dict["event"] = line[7:].strip()
            elif line.startswith("data: "):
                frame_dict["data"] = json.loads(line[6:].strip())

        assert "id" in frame_dict
        assert "event" in frame_dict
        assert "data" in frame_dict
        validator.validate(frame_dict, SSE_SCHEMA)
