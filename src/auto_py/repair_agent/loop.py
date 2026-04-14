from __future__ import annotations

from collections.abc import Callable

from auto_py.llm.gateway import LLMGateway, LLMRequest
from auto_py.repair_agent.context import FailureContext
from auto_py.repair_agent.prompts import build_repair_messages
from auto_py.repair_agent.result import RepairAttempt, RepairResult, ValidationResult

PatchValidator = Callable[[str, FailureContext], ValidationResult]


class RepairAgent:
    """Small patch-proposal loop around an LLM gateway.

    This is intentionally not a general coding agent. The model proposes a
    unified diff, then auto-py validates the candidate deterministically. Failed
    validation is fed back into the next proposal.
    """

    def __init__(
        self,
        gateway: LLMGateway,
        validator: PatchValidator,
        *,
        max_attempts: int = 3,
        max_tokens: int = 2048,
    ) -> None:
        self.gateway = gateway
        self.validator = validator
        self.max_attempts = max_attempts
        self.max_tokens = max_tokens

    def repair(self, context: FailureContext) -> RepairResult:
        attempts: list[RepairAttempt] = []

        for attempt_number in range(1, self.max_attempts + 1):
            request = LLMRequest(
                messages=build_repair_messages(context),
                temperature=0.0,
                max_tokens=self.max_tokens,
            )
            response = self.gateway.complete(request)
            diff_text = normalize_diff_response(response.text)

            validation = self.validator(diff_text, context)
            attempts.append(
                RepairAttempt(
                    attempt_number=attempt_number,
                    diff_text=diff_text,
                    validation=validation,
                )
            )

            if validation.ok:
                return RepairResult(ok=True, diff_text=diff_text, attempts=attempts)

            context.validation_feedback.append(
                f"Attempt {attempt_number} failed validation:\n{validation.to_feedback()}"
            )

        return RepairResult(
            ok=False,
            attempts=attempts,
            reason="Repair attempts exhausted without a valid patch.",
        )


def normalize_diff_response(response_text: str) -> str:
    """Strip common Markdown wrappers while keeping the diff unchanged."""
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text
