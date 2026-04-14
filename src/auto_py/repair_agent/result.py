from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ValidationResult:
    """Result from deterministic validation of a candidate patch."""

    ok: bool
    summary: str
    details: str = ""

    def to_feedback(self) -> str:
        if self.details:
            return f"{self.summary}\n{self.details}"
        return self.summary


@dataclass(slots=True)
class RepairAttempt:
    """One repair proposal and its validation result."""

    attempt_number: int
    diff_text: str
    validation: ValidationResult


@dataclass(slots=True)
class RepairResult:
    """Final outcome of the repair loop."""

    ok: bool
    diff_text: str | None = None
    attempts: list[RepairAttempt] = field(default_factory=list)
    reason: str = ""
