from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class LLMMessage:
    """Single chat message sent to an LLM gateway."""

    role: str
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass(slots=True)
class LLMRequest:
    """Provider-neutral request used by auto-py's repair loop."""

    messages: list[LLMMessage]
    model: str | None = None
    temperature: float = 0.0
    max_tokens: int | None = None
    response_format: dict[str, Any] | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class LLMResponse:
    """Provider-neutral response returned to the repair loop."""

    text: str
    model: str
    raw: dict[str, Any]


class LLMGateway(Protocol):
    """Minimal LLM interface so repair logic is not coupled to a provider."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Return a model response for a chat-style request."""
