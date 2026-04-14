from __future__ import annotations

from pathlib import Path

import typer

from auto_py.capture import execute_prepared_module
from auto_py.llm.config import (
    LLMGatewayConfig,
    default_config_path,
    load_llm_config,
    write_default_llm_config,
)
from auto_py.validate import PreparedModule, prepare_module

app = typer.Typer(
    add_completion=False,
    help="Run Python files through the auto-py workflow.",
)
llm_config_app = typer.Typer(
    add_completion=False,
    help="Manage local-first LLM gateway configuration.",
)


def parse_python_file(file_path: Path) -> PreparedModule:
    """Read, parse, and compile a Python file for execution."""
    while True:
        try:
            return prepare_module(file_path)
        except SyntaxError as error:
            print(f"[SYNTAX ERROR] {error}")
            print("[RESUME] Fix the file, then type 'r' and press Enter to retry parsing.")
            wait_for_manual_retry(error)


def execute_python_file(prepared_module: PreparedModule) -> None:
    """Execute a prepared Python module."""
    execute_prepared_module(prepared_module)


def wait_for_manual_retry(original_error: SyntaxError) -> None:
    """Block until the user requests another parse attempt."""
    while True:
        try:
            command = input().strip().lower()
        except EOFError as exc:
            raise original_error from exc

        if command == "r":
            return

        print("[RESUME] Waiting for 'r'.")


@app.command()
def run(file_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True)) -> None:
    """Run a Python file through the auto-py pipeline."""
    prepared_module = parse_python_file(file_path)
    execute_python_file(prepared_module)


@llm_config_app.command("path")
def llm_config_path() -> None:
    """Print the user-level LLM config path."""
    print(default_config_path())


@llm_config_app.command("init")
def init_llm_config(
    force: bool = typer.Option(False, "--force", help="Overwrite an existing config file."),
    base_url: str = typer.Option(LLMGatewayConfig().base_url, help="OpenAI-compatible gateway base URL."),
    model: str = typer.Option(LLMGatewayConfig().model, help="Model name to request from the gateway."),
    api_key_env: str = typer.Option(
        LLMGatewayConfig().api_key_env,
        help="Environment variable used for hosted gateway API keys.",
    ),
    timeout_seconds: float = typer.Option(LLMGatewayConfig().timeout_seconds, help="Request timeout in seconds."),
) -> None:
    """Create a local-first LLM config file."""
    config = LLMGatewayConfig(
        base_url=base_url,
        model=model,
        api_key_env=api_key_env,
        timeout_seconds=timeout_seconds,
    )
    try:
        path = write_default_llm_config(force=force, config=config)
    except FileExistsError as error:
        raise typer.BadParameter(str(error)) from error
    print(f"Wrote LLM config to {path}")


@llm_config_app.command("show")
def show_llm_config() -> None:
    """Print the resolved LLM config, including environment overrides."""
    config = load_llm_config()
    print(config.to_toml(), end="")


app.add_typer(llm_config_app, name="llm-config")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
