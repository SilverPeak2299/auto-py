from __future__ import annotations

import base64
import json
import pickle
from pathlib import Path

from auto_py.checkpoint import capture_function_checkpoint


def replayable_function(x: int, y: int, *, bias: int = 0) -> int:
    return x + y + bias


def test_captures_and_replays_function_entry_checkpoint(tmp_path: Path) -> None:
    script_path = tmp_path / "demo_script.py"
    script_path.write_text("def replayable_function(x, y, bias=0):\n    return x + y + bias\n", encoding="utf-8")

    record = capture_function_checkpoint(
        script_path=script_path,
        function_name="replayable_function",
        args=(2, 3),
        kwargs={"bias": 4},
    )

    checkpoint_path = Path(record.checkpoint_path or "")
    try:
        assert record.resume_kind == "function"
        assert checkpoint_path.exists()

        payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        assert payload["function_name"] == "replayable_function"
        assert payload["script_path"] == str(script_path.resolve())
        assert payload["source_hash"] == record.source_hash

        state_blob = base64.b64decode(payload["state_blob"])
        saved_state = pickle.loads(state_blob)

        result = replayable_function(*saved_state["args"], **saved_state["kwargs"])

        assert result == 9
    finally:
        if checkpoint_path.exists():
            checkpoint_path.unlink()
