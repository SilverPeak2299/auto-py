from __future__ import annotations

from pathlib import Path

import typer

from auto_py.capture import execute_prepared_module
from auto_py.validate import PreparedModule, prepare_module

app = typer.Typer(
    add_completion=False,
    help="Run Python files through the auto-py workflow.",
)


def parse_python_file(file_path: Path) -> PreparedModule:
    """Read, parse, and compile a Python file for execution."""
    return prepare_module(file_path)


def execute_python_file(prepared_module: PreparedModule) -> None:
    """Execute a prepared Python module."""
    execute_prepared_module(prepared_module)


@app.command()
def run(file_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True)) -> None:
    """Run a Python file through the auto-py pipeline."""
    prepared_module = parse_python_file(file_path)
    execute_python_file(prepared_module)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
