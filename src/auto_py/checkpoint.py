from __future__ import annotations

import base64
import hashlib
import json
import pickle
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping
from uuid import uuid4

CHECKPOINT_FORMAT_VERSION = 1


@dataclass(slots=True)
class CheckpointRecord:
    """Serializable record for a saved function-entry checkpoint."""

    checkpoint_id: str
    script_path: str
    source_hash: str
    repair_attempt: int
    resume_kind: str
    function_name: str
    step_id: str | None
    state_blob: bytes
    argv: list[str]
    cwd: str
    checkpoint_path: str | None = None
    format_version: int = CHECKPOINT_FORMAT_VERSION

    def to_dict(self) -> dict[str, object]:
        """Convert the checkpoint record into a JSON-safe dictionary."""
        payload = asdict(self)
        payload["state_blob"] = base64.b64encode(self.state_blob).decode("ascii")
        return payload


def serialize_function_state(
    args: tuple[object, ...],
    kwargs: Mapping[str, object] | None = None,
) -> bytes:
    """Serialize function-entry inputs for later replay."""
    payload = {
        "args": args,
        "kwargs": dict(kwargs or {}),
    }
    return pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)


def build_source_hash(script_path: Path) -> str:
    """Hash the current source file so checkpoints can be matched to repairs."""
    return hashlib.sha256(script_path.read_bytes()).hexdigest()


def save_checkpoint_record(
    record: CheckpointRecord,
    checkpoint_file: Path | None = None,
) -> Path:
    """Persist a checkpoint record to a temp file by default."""
    payload = json.dumps(record.to_dict(), indent=2, sort_keys=True)

    if checkpoint_file is not None:
        resolved_file_path = checkpoint_file.resolve()
        resolved_file_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_file_path.write_text(payload, encoding="utf-8")
        return resolved_file_path

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix="auto-py-checkpoint-",
        suffix=".json",
        delete=False,
    ) as temporary_file:
        temporary_file.write(payload)
        return Path(temporary_file.name).resolve()


def capture_function_checkpoint(
    script_path: Path,
    function_name: str,
    args: tuple[object, ...],
    kwargs: Mapping[str, object] | None = None,
    *,
    repair_attempt: int = 0,
    checkpoint_file: Path | None = None,
    argv: list[str] | None = None,
    cwd: Path | None = None,
) -> CheckpointRecord:
    """Create and persist a function-entry checkpoint without executing resume logic."""
    resolved_script_path = script_path.resolve()
    record = CheckpointRecord(
        checkpoint_id=str(uuid4()),
        script_path=str(resolved_script_path),
        source_hash=build_source_hash(resolved_script_path),
        repair_attempt=repair_attempt,
        resume_kind="function",
        function_name=function_name,
        step_id=None,
        state_blob=serialize_function_state(args, kwargs),
        argv=list(argv) if argv is not None else sys.argv[:],
        cwd=str((cwd or Path.cwd()).resolve()),
    )
    record.checkpoint_path = str(save_checkpoint_record(record, checkpoint_file=checkpoint_file))
    return record
