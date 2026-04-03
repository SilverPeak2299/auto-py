from __future__ import annotations

import ast
import sys
from contextlib import contextmanager
from pathlib import Path
from types import FrameType
from typing import Iterator

from auto_py.checkpoint import (
    CheckpointRecord,
    capture_function_frame_checkpoint,
    capture_module_checkpoint,
    deserialize_state_blob,
)
from auto_py.validate import PreparedModule, prepare_module


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
    active_checkpoint: CheckpointRecord | None = None

    def runtime_checkpoint(label: str) -> None:
        nonlocal active_checkpoint
        frame = sys._getframe(1)
        active_checkpoint = capture_runtime_checkpoint(prepared_module.path, label, frame)

    namespace["__auto_py_checkpoint__"] = runtime_checkpoint

    with script_runtime_context(prepared_module.path, script_args=script_args):
        try:
            exec(prepared_module.code, namespace, namespace)
        except Exception as error:
            if active_checkpoint is None:
                raise
            return wait_for_manual_resume(
                checkpoint=active_checkpoint,
                original_error=error,
                script_args=script_args,
            )
    return namespace


def capture_runtime_checkpoint(
    script_path: Path,
    checkpoint_label: str,
    frame: FrameType,
) -> CheckpointRecord:
    """Capture a manual runtime checkpoint from the current module frame."""
    if frame.f_code.co_name == "<module>":
        return capture_module_checkpoint(script_path, checkpoint_label, frame.f_globals)
    return capture_function_frame_checkpoint(
        script_path,
        function_name=frame.f_code.co_name,
        checkpoint_label=checkpoint_label,
        globals_snapshot=frame.f_globals,
        locals_snapshot=frame.f_locals,
    )


def wait_for_manual_resume(
    checkpoint: CheckpointRecord,
    original_error: Exception,
    script_args: list[str] | None = None,
) -> dict[str, object]:
    """Pause after an exception until the user requests a resume attempt."""
    print(f"[ERROR] {original_error}")
    print(f"[CHECKPOINT] {checkpoint.step_id} saved at {checkpoint.checkpoint_path}")
    print("[RESUME] Fix the file, then type 'r' and press Enter to resume.")

    while True:
        try:
            command = input().strip().lower()
        except EOFError as exc:
            raise original_error from exc

        if command != "r":
            print("[RESUME] Waiting for 'r'.")
            continue

        try:
            return resume_from_checkpoint(checkpoint, script_args=script_args)
        except Exception as resume_error:
            print(f"[RESUME ERROR] {resume_error}")
            print("[RESUME] Fix the file, then type 'r' to try again.")


def resume_from_checkpoint(
    checkpoint: CheckpointRecord,
    script_args: list[str] | None = None,
) -> dict[str, object]:
    """Reload the repaired script and resume execution after a module checkpoint."""
    if checkpoint.resume_kind == "module":
        return resume_module_checkpoint(checkpoint, script_args=script_args)
    if checkpoint.resume_kind == "function_frame":
        return resume_function_checkpoint(checkpoint, script_args=script_args)
    raise ValueError(f"Unsupported checkpoint kind: {checkpoint.resume_kind}")


def resume_module_checkpoint(
    checkpoint: CheckpointRecord,
    script_args: list[str] | None = None,
) -> dict[str, object]:
    """Reload the repaired script and resume execution after a module checkpoint."""
    if checkpoint.step_id is None:
        raise ValueError("Module checkpoint is missing a checkpoint label.")

    repaired_module = prepare_module(Path(checkpoint.script_path))
    checkpoint_index = find_module_checkpoint_index(repaired_module.tree, checkpoint.step_id)
    prefix_tree = ast.Module(body=repaired_module.tree.body[:checkpoint_index], type_ignores=[])
    suffix_tree = ast.Module(body=repaired_module.tree.body[checkpoint_index + 1 :], type_ignores=[])
    ast.fix_missing_locations(prefix_tree)
    ast.fix_missing_locations(suffix_tree)

    namespace = build_execution_namespace(repaired_module.path)
    active_checkpoint: CheckpointRecord | None = None

    def runtime_checkpoint(label: str) -> None:
        nonlocal active_checkpoint
        frame = sys._getframe(1)
        active_checkpoint = capture_runtime_checkpoint(repaired_module.path, label, frame)

    namespace["__auto_py_checkpoint__"] = runtime_checkpoint

    restored_state = deserialize_state_blob(checkpoint.state_blob)

    with script_runtime_context(repaired_module.path, script_args=script_args):
        exec(compile(prefix_tree, str(repaired_module.path), "exec"), namespace, namespace)
        namespace.update(restored_state)
        try:
            exec(compile(suffix_tree, str(repaired_module.path), "exec"), namespace, namespace)
        except Exception as error:
            if active_checkpoint is None:
                raise
            return wait_for_manual_resume(
                checkpoint=active_checkpoint,
                original_error=error,
                script_args=script_args,
            )

    return namespace


def resume_function_checkpoint(
    checkpoint: CheckpointRecord,
    script_args: list[str] | None = None,
) -> dict[str, object]:
    """Reload the repaired script and resume execution inside a checkpointed function."""
    if checkpoint.step_id is None:
        raise ValueError("Function checkpoint is missing a checkpoint label.")

    repaired_module = prepare_module(Path(checkpoint.script_path))
    function_node, checkpoint_index = find_function_checkpoint(repaired_module.tree, checkpoint.step_id)
    bootstrap_tree = build_function_resume_bootstrap_tree(repaired_module.tree)
    resume_parameter_names = extract_resume_parameter_names(function_node, checkpoint_index)
    resume_tree = build_function_resume_tree(function_node, checkpoint_index, resume_parameter_names)

    namespace = build_execution_namespace(repaired_module.path)
    active_checkpoint: CheckpointRecord | None = None

    def runtime_checkpoint(label: str) -> None:
        nonlocal active_checkpoint
        frame = sys._getframe(1)
        active_checkpoint = capture_runtime_checkpoint(repaired_module.path, label, frame)

    namespace["__auto_py_checkpoint__"] = runtime_checkpoint

    restored_state = deserialize_state_blob(checkpoint.state_blob)
    restored_globals = restored_state.get("globals", {})
    restored_locals = {
        name: value
        for name, value in restored_state.get("locals", {}).items()
        if name in resume_parameter_names
    }

    with script_runtime_context(repaired_module.path, script_args=script_args):
        exec(compile(bootstrap_tree, str(repaired_module.path), "exec"), namespace, namespace)
        namespace.update(restored_globals)
        exec(compile(resume_tree, str(repaired_module.path), "exec"), namespace, namespace)
        try:
            resume_function = namespace[function_node.name]
            resume_function(**restored_locals)
        except Exception as error:
            if active_checkpoint is None:
                raise
            return wait_for_manual_resume(
                checkpoint=active_checkpoint,
                original_error=error,
                script_args=script_args,
            )

    return namespace


def find_module_checkpoint_index(tree: ast.Module, checkpoint_label: str) -> int:
    """Locate the module-scope checkpoint call matching the saved label."""
    for index, statement in enumerate(tree.body):
        if not isinstance(statement, ast.Expr):
            continue
        call = statement.value
        if not isinstance(call, ast.Call):
            continue
        if not isinstance(call.func, ast.Name) or call.func.id != "__auto_py_checkpoint__":
            continue
        if not call.args:
            continue
        label = call.args[0]
        if isinstance(label, ast.Constant) and label.value == checkpoint_label:
            return index

    raise ValueError(f"Could not find checkpoint label {checkpoint_label!r} in repaired source.")


def find_function_checkpoint(
    tree: ast.Module,
    checkpoint_label: str,
) -> tuple[ast.FunctionDef | ast.AsyncFunctionDef, int]:
    """Locate a function-scope checkpoint call matching the saved label."""
    for statement in tree.body:
        if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for index, body_statement in enumerate(statement.body):
            if is_checkpoint_statement(body_statement, checkpoint_label):
                return statement, index

    raise ValueError(f"Could not find function checkpoint label {checkpoint_label!r} in repaired source.")


def is_checkpoint_statement(statement: ast.stmt, checkpoint_label: str) -> bool:
    """Return True when a statement is a checkpoint call for the given label."""
    if not isinstance(statement, ast.Expr):
        return False
    call = statement.value
    if not isinstance(call, ast.Call):
        return False
    if not isinstance(call.func, ast.Name) or call.func.id != "__auto_py_checkpoint__":
        return False
    if not call.args:
        return False
    label = call.args[0]
    return isinstance(label, ast.Constant) and label.value == checkpoint_label


def build_function_resume_bootstrap_tree(tree: ast.Module) -> ast.Module:
    """Build module code that recreates definitions without rerunning the main guard."""
    bootstrap_body: list[ast.stmt] = []

    for statement in tree.body:
        if is_main_guard(statement):
            continue
        bootstrap_body.append(statement)

    bootstrap_tree = ast.Module(body=bootstrap_body, type_ignores=tree.type_ignores)
    ast.fix_missing_locations(bootstrap_tree)
    return bootstrap_tree


def build_function_resume_tree(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
    checkpoint_index: int,
    resume_parameter_names: list[str],
) -> ast.Module:
    """Build a synthetic function definition that resumes after the checkpoint."""
    resume_parameters = [ast.arg(arg=name) for name in resume_parameter_names]
    resume_args = ast.arguments(
        posonlyargs=[],
        args=resume_parameters,
        vararg=None,
        kwonlyargs=[],
        kw_defaults=[],
        kwarg=None,
        defaults=[],
    )
    resume_body = function_node.body[checkpoint_index + 1 :]

    if not resume_body:
        resume_body = [ast.Pass()]

    if isinstance(function_node, ast.AsyncFunctionDef):
        resume_function = ast.AsyncFunctionDef(
            name=function_node.name,
            args=resume_args,
            body=resume_body,
            decorator_list=[],
            returns=function_node.returns,
            type_comment=function_node.type_comment,
        )
    else:
        resume_function = ast.FunctionDef(
            name=function_node.name,
            args=resume_args,
            body=resume_body,
            decorator_list=[],
            returns=function_node.returns,
            type_comment=function_node.type_comment,
        )

    resume_tree = ast.Module(body=[resume_function], type_ignores=[])
    ast.fix_missing_locations(resume_tree)
    return resume_tree


def extract_resume_parameter_names(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
    checkpoint_index: int,
) -> list[str]:
    """Collect the local names that need to be restored for a resumed function."""
    parameter_names: list[str] = []
    seen_names: set[str] = set()

    all_parameters = [
        *function_node.args.posonlyargs,
        *function_node.args.args,
        *function_node.args.kwonlyargs,
    ]
    if function_node.args.vararg is not None:
        all_parameters.append(function_node.args.vararg)
    if function_node.args.kwarg is not None:
        all_parameters.append(function_node.args.kwarg)

    for parameter in all_parameters:
        if parameter.arg in seen_names:
            continue
        seen_names.add(parameter.arg)
        parameter_names.append(parameter.arg)

    for statement in function_node.body[:checkpoint_index]:
        for name in collect_assigned_names(statement):
            if name in seen_names:
                continue
            seen_names.add(name)
            parameter_names.append(name)

    return parameter_names


def collect_assigned_names(statement: ast.stmt) -> list[str]:
    """Collect simple local names assigned before a checkpoint."""
    assigned_names: list[str] = []

    for node in ast.walk(statement):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            assigned_names.append(node.id)

    return assigned_names


def is_main_guard(statement: ast.stmt) -> bool:
    """Return True when a module statement is `if __name__ == "__main__":`."""
    if not isinstance(statement, ast.If):
        return False

    test = statement.test
    if not isinstance(test, ast.Compare):
        return False
    if len(test.ops) != 1 or len(test.comparators) != 1:
        return False
    if not isinstance(test.ops[0], ast.Eq):
        return False
    if not isinstance(test.left, ast.Name) or test.left.id != "__name__":
        return False

    comparator = test.comparators[0]
    return isinstance(comparator, ast.Constant) and comparator.value == "__main__"
