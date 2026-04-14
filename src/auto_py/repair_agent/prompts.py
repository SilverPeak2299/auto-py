from __future__ import annotations

from auto_py.llm.gateway import LLMMessage
from auto_py.repair_agent.context import FailureContext

SYSTEM_PROMPT = """You are the repair component of auto-py.

auto-py is a checkpoint-aware Python runtime repair tool. Your job is to
propose a minimal unified diff that fixes the reported runtime failure.

Rules:
- Return one unified diff only.
- Do not include Markdown fences.
- Prefer the smallest source change that addresses the failure.
- Preserve checkpoint calls and checkpoint comments.
- Do not rewrite unrelated code.
- Do not claim validation has passed; auto-py validates candidates itself.
- If previous validation feedback is present, revise the patch to address it.
"""


def build_repair_messages(context: FailureContext) -> list[LLMMessage]:
    return [
        LLMMessage(role="system", content=SYSTEM_PROMPT),
        LLMMessage(
            role="user",
            content=(
                "Generate a unified diff for this Python runtime failure.\n\n"
                f"{context.to_prompt_text()}"
            ),
        ),
    ]
