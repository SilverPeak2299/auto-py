from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from auto_py.llm.config import (
    DEFAULT_LOCAL_BASE_URL,
    DEFAULT_LOCAL_MODEL,
    LLMGatewayConfig,
    load_llm_config,
)
from auto_py.llm.gateway import LLMRequest, LLMResponse


@dataclass(slots=True)
class OpenAICompatibleConfig:
    """Configuration for local or hosted OpenAI-compatible chat APIs."""

    base_url: str = DEFAULT_LOCAL_BASE_URL
    model: str = DEFAULT_LOCAL_MODEL
    api_key: str | None = None
    timeout_seconds: float = 120.0

    @classmethod
    def from_env(cls) -> OpenAICompatibleConfig:
        """Build config from user config plus environment overrides."""
        gateway_config = load_llm_config()
        return cls.from_gateway_config(gateway_config)

    @classmethod
    def from_gateway_config(cls, config: LLMGatewayConfig) -> OpenAICompatibleConfig:
        return cls(
            base_url=config.base_url,
            model=config.model,
            api_key=config.api_key(),
            timeout_seconds=config.timeout_seconds,
        )


class OpenAICompatibleGateway:
    """Tiny stdlib client for OpenAI-compatible local model servers.

    This intentionally targets the common `/chat/completions` shape used by
    local runtimes such as Ollama, LM Studio, Docker Model Runner, llama.cpp,
    and cloud gateways. Provider-specific behavior belongs behind this class,
    not inside the repair agent.
    """

    def __init__(self, config: OpenAICompatibleConfig | None = None) -> None:
        self.config = config or OpenAICompatibleConfig.from_env()

    def complete(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self.config.model
        payload: dict[str, Any] = {
            "model": model,
            "messages": [message.to_dict() for message in request.messages],
            "temperature": request.temperature,
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.response_format is not None:
            payload["response_format"] = request.response_format

        response_payload = self._post_json("/chat/completions", payload)
        return LLMResponse(
            text=_extract_chat_text(response_payload),
            model=str(response_payload.get("model") or model),
            raw=response_payload,
        )

    def _post_json(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        base_url = self.config.base_url.rstrip("/")
        url = f"{base_url}{endpoint}"
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        request = urllib.request.Request(url, data=body, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM gateway request failed with HTTP {error.code}: {detail}") from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"LLM gateway request failed: {error.reason}") from error


def _extract_chat_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("LLM gateway response did not include any choices.")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise RuntimeError("LLM gateway response choice was not an object.")

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("LLM gateway response did not include a message.")

    content = message.get("content")
    if not isinstance(content, str):
        raise RuntimeError("LLM gateway response message did not include text content.")

    return content
