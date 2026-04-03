from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from auto_py.validate import PreparedModule


def build_execution_namespace(file_path: Path) -> dict[str, object]:
    """Create a module-style namespace for executing a script."""
    return {
        "__name__": "__main__",
        "__file__": str(file_path),
        "__package__": None,
        "__builtins__": __builtins__,
    }


@contextmanager
def script_runtime_context(file_path: Path, script_args: list[str] | None = None) -> Iterator[None]:
    """Temporarily mirror the runtime context Python uses for scripts."""
    original_argv = sys.argv[:]
    original_path = sys.path[:]
    resolved_path = file_path.resolve()
    args = script_args or []

    try:
        sys.argv = [str(resolved_path), *args]
        sys.path = [str(resolved_path.parent), *original_path]
        yield
    finally:
        sys.argv = original_argv
        sys.path = original_path


def execute_prepared_module(
    prepared_module: PreparedModule,
    script_args: list[str] | None = None,
) -> dict[str, object]:
    """Execute compiled module code inside an isolated module namespace."""
    namespace = build_execution_namespace(prepared_module.path)
    with script_runtime_context(prepared_module.path, script_args=script_args):
        exec(prepared_module.code, namespace, namespace)
    return namespace
