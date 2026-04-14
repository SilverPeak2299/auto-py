from __future__ import annotations

import os
import platform
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_LLM_PROVIDER = "openai-compatible"
DEFAULT_LOCAL_BASE_URL = "http://localhost:11434/v1"
DEFAULT_LOCAL_MODEL = "qwen2.5-coder:7b"
DEFAULT_API_KEY_ENV = "AUTO_PY_LLM_API_KEY"
DEFAULT_LLM_TIMEOUT_SECONDS = 120.0
CONFIG_PATH_ENV = "AUTO_PY_CONFIG"


@dataclass(slots=True)
class LLMGatewayConfig:
    """User-facing LLM gateway config.

    The defaults target a local OpenAI-compatible model server, usually Ollama.
    Hosted providers and gateways can be reached by changing the base URL/model
    without changing the repair agent.
    """

    provider: str = DEFAULT_LLM_PROVIDER
    base_url: str = DEFAULT_LOCAL_BASE_URL
    model: str = DEFAULT_LOCAL_MODEL
    api_key_env: str = DEFAULT_API_KEY_ENV
    timeout_seconds: float = DEFAULT_LLM_TIMEOUT_SECONDS

    def api_key(self) -> str | None:
        value = os.getenv(self.api_key_env)
        if value:
            return value
        return None

    def with_env_overrides(self) -> LLMGatewayConfig:
        """Apply environment variables without mutating the loaded config."""
        return LLMGatewayConfig(
            provider=os.getenv("AUTO_PY_LLM_PROVIDER", self.provider),
            base_url=os.getenv("AUTO_PY_LLM_BASE_URL", self.base_url),
            model=os.getenv("AUTO_PY_LLM_MODEL", self.model),
            api_key_env=os.getenv("AUTO_PY_LLM_API_KEY_ENV", self.api_key_env),
            timeout_seconds=float(os.getenv("AUTO_PY_LLM_TIMEOUT", str(self.timeout_seconds))),
        )

    def to_toml(self) -> str:
        return (
            "[llm]\n"
            f'provider = "{_escape_toml_string(self.provider)}"\n'
            f'base_url = "{_escape_toml_string(self.base_url)}"\n'
            f'model = "{_escape_toml_string(self.model)}"\n'
            f'api_key_env = "{_escape_toml_string(self.api_key_env)}"\n'
            f"timeout_seconds = {self.timeout_seconds:g}\n"
        )


def default_config_path() -> Path:
    """Return the per-user config path suitable for pipx installs."""
    override = os.getenv(CONFIG_PATH_ENV)
    if override:
        return Path(override).expanduser()

    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "auto-py" / "config.toml"
    if system == "Windows":
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata) / "auto-py" / "config.toml"

    config_home = os.getenv("XDG_CONFIG_HOME")
    if config_home:
        return Path(config_home) / "auto-py" / "config.toml"
    return Path.home() / ".config" / "auto-py" / "config.toml"


def load_llm_config(config_path: Path | None = None, *, apply_env: bool = True) -> LLMGatewayConfig:
    """Load LLM config from disk, falling back to local-first defaults."""
    path = config_path or default_config_path()
    config = LLMGatewayConfig()

    if path.exists():
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        config = _config_from_toml_data(data)

    if apply_env:
        return config.with_env_overrides()
    return config


def write_default_llm_config(
    config_path: Path | None = None,
    *,
    force: bool = False,
    config: LLMGatewayConfig | None = None,
) -> Path:
    """Write a local-first config file and return its path."""
    path = config_path or default_config_path()
    if path.exists() and not force:
        raise FileExistsError(f"Config already exists: {path}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text((config or LLMGatewayConfig()).to_toml(), encoding="utf-8")
    return path


def _config_from_toml_data(data: dict[str, Any]) -> LLMGatewayConfig:
    llm_data = data.get("llm", {})
    if not isinstance(llm_data, dict):
        raise ValueError("Config [llm] section must be a table.")

    return LLMGatewayConfig(
        provider=_string_value(llm_data, "provider", DEFAULT_LLM_PROVIDER),
        base_url=_string_value(llm_data, "base_url", DEFAULT_LOCAL_BASE_URL),
        model=_string_value(llm_data, "model", DEFAULT_LOCAL_MODEL),
        api_key_env=_string_value(llm_data, "api_key_env", DEFAULT_API_KEY_ENV),
        timeout_seconds=_float_value(llm_data, "timeout_seconds", DEFAULT_LLM_TIMEOUT_SECONDS),
    )


def _string_value(data: dict[str, Any], key: str, default: str) -> str:
    value = data.get(key, default)
    if not isinstance(value, str):
        raise ValueError(f"Config value llm.{key} must be a string.")
    return value


def _float_value(data: dict[str, Any], key: str, default: float) -> float:
    value = data.get(key, default)
    if not isinstance(value, int | float):
        raise ValueError(f"Config value llm.{key} must be a number.")
    return float(value)


def _escape_toml_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
