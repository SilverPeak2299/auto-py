# Repository Guidelines

## Project Structure & Module Organization
This repository is currently documentation-first. `README.md` describes the CLI goal and expected package layout, while `docs/PRD.md` captures product requirements and milestones.

When implementation files are added, follow the structure already described in the README:
- `src/runner.py` for CLI orchestration
- `src/capture.py` for exception/context capture
- `src/checkpoint.py` for controlled re-execution
- `src/validate.py` for syntax/runtime validation
- `src/repair.py` for LLM-driven repair
- `examples/` for reproducible failing scripts used in demos and tests

Keep new modules focused on one stage of the repair pipeline.

## Build, Test, and Development Commands
Use `uv` from the repository root so local development matches the eventual `pipx` install flow.

- `uv venv` creates the local virtual environment
- `.venv\Scripts\Activate.ps1` activates it in PowerShell
- `uv sync` installs project and dev dependencies from `pyproject.toml` / `uv.lock`
- `uv run pytest` runs the test suite once `tests/` is added
- `uv run auto-py script.py` exercises the installed CLI entry point
- `uv build` produces source and wheel distributions for publishing

Keep packaging metadata in `pyproject.toml`, including the console script entry point for `auto-py`, so `pipx install auto-py` works from a published distribution.

## Coding Style & Naming Conventions
Target Python 3 with 4-space indentation and PEP 8 naming:
- `snake_case` for modules, functions, and variables
- `PascalCase` for classes
- short, explicit function names such as `capture_failure_context`

Prefer type hints on public functions and small, composable modules over large orchestration files. Format with `ruff format` and lint with `ruff check`; keep tool configuration in `pyproject.toml`.

## Testing Guidelines
Place tests under `tests/` and mirror the source layout, for example `tests/test_validate.py`. Name tests after observable behavior, such as `test_rejects_invalid_python_fix`.

Focus coverage on deterministic failure capture, validation rejection, retry limits, and safe checkpoint re-execution. Add at least one example script for each repaired failure mode.

## Commit & Pull Request Guidelines
The current history starts with `Initial commit`, so adopt short, imperative commit subjects going forward, for example `Add AST validation for candidate fixes`.

Pull requests should include:
- a concise summary of behavior changes
- linked issue or milestone when relevant
- test evidence (`uv run pytest`, example run output, or both)
- screenshots or terminal snippets only when CLI output changes materially

## Packaging Notes
Design the project as an installable CLI package from the start. Before publishing, verify the package name, version, Python requirement, and console script in `pyproject.toml`, then confirm the built wheel works with `pipx`.

Do not mix documentation-only and runtime-behavior changes in the same PR unless tightly coupled.
