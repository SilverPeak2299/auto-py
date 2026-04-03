from __future__ import annotations

import ast
import tokenize
from dataclasses import dataclass
from pathlib import Path
from types import CodeType


@dataclass(slots=True)
class PreparedModule:
    """Container for the parsed and compiled Python module."""

    path: Path
    source: str
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


def prepare_module(file_path: Path) -> PreparedModule:
    """Read, parse, and compile a Python file for execution."""
    resolved_path = file_path.resolve()
    source = read_python_source(resolved_path)
    tree = parse_python_source(source, filename=str(resolved_path))
    code = compile_module_ast(tree, filename=str(resolved_path))
    return PreparedModule(path=resolved_path, source=source, tree=tree, code=code)
