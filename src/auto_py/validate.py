from __future__ import annotations

import ast
import re
import tokenize
from dataclasses import dataclass
from pathlib import Path
from types import CodeType

CHECKPOINT_PATTERN = re.compile(r"^(?P<indent>[ \t]*)#\s*CHECKPOINT(?:\s+(?P<label>[A-Za-z0-9_-]+))?\s*$")


@dataclass(slots=True)
class PreparedModule:
    """Container for the parsed and compiled Python module."""

    path: Path
    source: str
    instrumented_source: str
    tree: ast.Module
    code: CodeType


def read_python_source(file_path: Path) -> str:
    """Read a Python source file while respecting encoding cookies."""
    with tokenize.open(file_path) as source_file:
        return source_file.read()


def parse_python_source(source: str, filename: str) -> ast.Module:
    """Parse source text into a module AST."""
    return ast.parse(source, filename=filename, mode="exec")


def compile_module_ast(tree: ast.AST, filename: str) -> CodeType:
    """Compile a module AST into an executable code object."""
    return compile(tree, filename, "exec")


def inject_checkpoint_calls(source: str) -> str:
    """Replace manual checkpoint markers with runtime checkpoint calls."""
    instrumented_lines: list[str] = []
    checkpoint_index = 0

    for line in source.splitlines(keepends=True):
        match = CHECKPOINT_PATTERN.match(line.rstrip("\n"))
        if not match:
            instrumented_lines.append(line)
            continue

        checkpoint_index += 1
        label = match.group("label") or f"checkpoint_{checkpoint_index}"
        indent = match.group("indent")
        newline = "\n" if line.endswith("\n") else ""
        instrumented_lines.append(f'{indent}__auto_py_checkpoint__("{label}"){newline}')

    return "".join(instrumented_lines)


def prepare_module(file_path: Path) -> PreparedModule:
    """Read, parse, and compile a Python file for execution."""
    resolved_path = file_path.resolve()
    source = read_python_source(resolved_path)
    instrumented_source = inject_checkpoint_calls(source)
    tree = parse_python_source(instrumented_source, filename=str(resolved_path))
    code = compile_module_ast(tree, filename=str(resolved_path))
    return PreparedModule(
        path=resolved_path,
        source=source,
        instrumented_source=instrumented_source,
        tree=tree,
        code=code,
    )
