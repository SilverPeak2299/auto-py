from __future__ import annotations

from auto_py.llm.config import DEFAULT_LLM_PROVIDER, LLMGatewayConfig, load_llm_config
from auto_py.llm.gateway import LLMGateway
from auto_py.llm.openai_compatible import OpenAICompatibleConfig, OpenAICompatibleGateway


def build_llm_gateway(config: LLMGatewayConfig | None = None) -> LLMGateway:
    """Build the configured LLM gateway.

    Only OpenAI-compatible gateways are implemented today because that covers
    local model servers and most hosted gateway products.
    """
    resolved_config = config or load_llm_config()

    if resolved_config.provider == DEFAULT_LLM_PROVIDER:
        return OpenAICompatibleGateway(OpenAICompatibleConfig.from_gateway_config(resolved_config))

    raise ValueError(f"Unsupported LLM provider: {resolved_config.provider}")
