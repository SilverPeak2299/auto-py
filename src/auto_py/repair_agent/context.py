from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class StateValueSummary:
    """Safe, prompt-oriented summary of a runtime value."""

    type_name: str
    repr_text: str
    serializable: bool


@dataclass(slots=True)
class CheckpointSummary:
    """Repair-facing view of a checkpoint without exposing raw pickle state."""

    checkpoint_id: str
    resume_kind: str
    function_name: str
    step_id: str | None
    script_path: Path
    repair_attempt: int
    locals: dict[str, StateValueSummary] = field(default_factory=dict)
    globals: dict[str, StateValueSummary] = field(default_factory=dict)


@dataclass(slots=True)
class FailureContext:
    """Structured failure packet passed into the repair agent."""

    script_path: Path
    exception_type: str
    exception_message: str
    traceback_text: str
    failing_line: int | None = None
    function_name: str | None = None
    source_snippet: str = ""
    checkpoint: CheckpointSummary | None = None
    validation_feedback: list[str] = field(default_factory=list)

    def to_prompt_text(self) -> str:
        checkpoint_text = "None"
        if self.checkpoint is not None:
            checkpoint_text = (
                f"id={self.checkpoint.checkpoint_id}\n"
                f"kind={self.checkpoint.resume_kind}\n"
                f"function={self.checkpoint.function_name}\n"
                f"step={self.checkpoint.step_id}\n"
                f"locals={list(self.checkpoint.locals)}"
            )

        feedback = "\n".join(self.validation_feedback) or "None"

        return (
            f"Script: {self.script_path}\n"
            f"Exception: {self.exception_type}: {self.exception_message}\n"
            f"Function: {self.function_name or 'unknown'}\n"
            f"Failing line: {self.failing_line or 'unknown'}\n\n"
            f"Checkpoint:\n{checkpoint_text}\n\n"
            f"Traceback:\n{self.traceback_text}\n\n"
            f"Source snippet:\n{self.source_snippet}\n\n"
            f"Validation feedback:\n{feedback}\n"
        )
