from __future__ import annotations

from dataclasses import dataclass

from auto_py.llm.gateway import LLMRequest, LLMResponse
from auto_py.llm.config import LLMGatewayConfig, load_llm_config, write_default_llm_config
from auto_py.llm.openai_compatible import (
    DEFAULT_LOCAL_BASE_URL,
    DEFAULT_LOCAL_MODEL,
    OpenAICompatibleConfig,
)
from auto_py.repair_agent.context import FailureContext
from auto_py.repair_agent.loop import RepairAgent, normalize_diff_response
from auto_py.repair_agent.prompts import build_repair_messages
from auto_py.repair_agent.result import ValidationResult


@dataclass
class FakeGateway:
    responses: list[str]
    requests: list[LLMRequest]

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(text=self.responses.pop(0), model="fake-local", raw={})


def test_local_gateway_config_defaults_to_local_model(monkeypatch) -> None:
    monkeypatch.setenv("AUTO_PY_CONFIG", "/tmp/auto-py-test-missing-config.toml")
    monkeypatch.delenv("AUTO_PY_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("AUTO_PY_LLM_MODEL", raising=False)
    monkeypatch.delenv("AUTO_PY_LLM_API_KEY", raising=False)

    config = OpenAICompatibleConfig.from_env()

    assert config.base_url == DEFAULT_LOCAL_BASE_URL
    assert config.model == DEFAULT_LOCAL_MODEL
    assert config.api_key is None


def test_llm_config_round_trips_to_toml(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("AUTO_PY_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("AUTO_PY_LLM_MODEL", raising=False)
    path = tmp_path / "config.toml"
    original = LLMGatewayConfig(
        base_url="http://localhost:1234/v1",
        model="local-coder",
        api_key_env="LOCAL_MODEL_KEY",
        timeout_seconds=30,
    )

    written_path = write_default_llm_config(path, config=original)
    loaded = load_llm_config(written_path, apply_env=False)

    assert written_path == path
    assert loaded.base_url == "http://localhost:1234/v1"
    assert loaded.model == "local-coder"
    assert loaded.api_key_env == "LOCAL_MODEL_KEY"
    assert loaded.timeout_seconds == 30


def test_llm_config_applies_env_overrides(tmp_path, monkeypatch) -> None:
    path = tmp_path / "config.toml"
    write_default_llm_config(path)
    monkeypatch.setenv("AUTO_PY_LLM_BASE_URL", "http://localhost:9999/v1")
    monkeypatch.setenv("AUTO_PY_LLM_MODEL", "override-model")

    loaded = load_llm_config(path)

    assert loaded.base_url == "http://localhost:9999/v1"
    assert loaded.model == "override-model"


def test_repair_prompt_contains_failure_context(tmp_path) -> None:
    context = FailureContext(
        script_path=tmp_path / "broken.py",
        exception_type="ZeroDivisionError",
        exception_message="division by zero",
        traceback_text="Traceback...",
        failing_line=4,
        function_name="main",
        source_snippet="x = 1 / 0",
    )

    messages = build_repair_messages(context)

    assert messages[0].role == "system"
    assert messages[1].role == "user"
    assert "ZeroDivisionError: division by zero" in messages[1].content
    assert "x = 1 / 0" in messages[1].content


def test_normalize_diff_response_strips_markdown_fence() -> None:
    response = """```diff
--- a/main.py
+++ b/main.py
@@ -1 +1 @@
-x = 1 / 0
+x = 1
```"""

    assert normalize_diff_response(response).startswith("--- a/main.py")
    assert "```" not in normalize_diff_response(response)


def test_repair_agent_retries_with_validation_feedback(tmp_path) -> None:
    context = FailureContext(
        script_path=tmp_path / "broken.py",
        exception_type="NameError",
        exception_message="name 'value' is not defined",
        traceback_text="Traceback...",
        source_snippet="print(value)",
    )
    gateway = FakeGateway(
        responses=[
            "--- a/broken.py\n+++ b/broken.py\n@@ -1 +1 @@\n-print(value)\n+print(missing)\n",
            "--- a/broken.py\n+++ b/broken.py\n@@ -1 +1 @@\n-print(value)\n+print('ok')\n",
        ],
        requests=[],
    )

    def validator(diff_text: str, _: FailureContext) -> ValidationResult:
        if "missing" in diff_text:
            return ValidationResult(ok=False, summary="compile failed", details="NameError risk")
        return ValidationResult(ok=True, summary="valid")

    result = RepairAgent(gateway, validator, max_attempts=2).repair(context)

    assert result.ok is True
    assert result.diff_text is not None
    assert "print('ok')" in result.diff_text
    assert len(result.attempts) == 2
    assert "Attempt 1 failed validation" in gateway.requests[1].messages[1].content
