# Checkpointing and Runtime Resolution

## Purpose

This document describes how `auto-py` should checkpoint execution state, apply a repair to the source file, and resume execution against the repaired program.

The central design requirement is:

1. A failure occurs.
2. The source file is repaired first.
3. The repaired source is parsed and compiled.
4. Execution resumes from a saved checkpoint against the repaired code.

This is not the same as restoring a full Python interpreter snapshot. The design here is based on replayable boundaries and explicit runtime state, not raw frame serialization.

## Core Principle

The checkpoint should not attempt to store the entire live interpreter state.

In normal Python execution, the following are not reliable to serialize and restore in a general way:

- live stack frames
- instruction pointers
- open file handles
- sockets
- generators and async tasks
- arbitrary C-extension objects
- partially-mutated global module state

Instead, `auto-py` should treat checkpoints as resumable boundaries.

That means each checkpoint stores:

- where execution can restart
- the serializable state needed to restart there
- enough metadata to ensure the checkpoint still matches the repaired code

## What the AST Is For

The AST is useful for:

- parsing the repaired source into a structured representation
- validating that the repaired program is syntactically valid
- injecting checkpoint hooks into the code
- assigning stable checkpoint labels to functions or steps
- recompiling the repaired code before resume

The AST is not the runtime state by itself.

Saving the AST alone does not capture:

- current locals
- current call stack
- loop progress
- return values already computed
- side effects already performed

The AST should define resumable boundaries. The checkpoint file should hold the runtime data.

## Checkpoint Models

### 1. Function-Entry Checkpoints

This should be the first implementation.

At the beginning of a checkpointed function, save:

- function identifier
- serialized `args`
- serialized `kwargs`
- script path
- source hash
- repair attempt number

If execution fails later, `auto-py` should:

1. repair the source file
2. parse and compile the repaired file
3. reload the module namespace
4. locate the saved function in the repaired code
5. deserialize the saved inputs
6. call the function again from the start

This does not resume in the middle of the function. It replays from the function boundary.

This is the simplest version that matches the PRD and is realistic for Python.

### 2. Step-Based Checkpoints Inside Functions

This is the next stage after function-entry replay.

Here the AST is transformed so a function becomes a resumable step machine. Instead of only storing inputs, the checkpoint also stores a program counter and selected local state.

Conceptually:

```python
def foo(x, y):
    a = step1(x)
    b = step2(a, y)
    return step3(b)
```

becomes:

```python
def foo(x, y, __checkpoint=None):
    state = __checkpoint or {"pc": 0, "x": x, "y": y}

    if state["pc"] <= 0:
        state["a"] = step1(state["x"])
        state["pc"] = 1
        save_checkpoint("foo", state)

    if state["pc"] <= 1:
        state["b"] = step2(state["a"], state["y"])
        state["pc"] = 2
        save_checkpoint("foo", state)

    if state["pc"] <= 2:
        state["result"] = step3(state["b"])
        state["pc"] = 3
        save_checkpoint("foo", state)

    return state["result"]
```

In this model, resume means:

- load the repaired source
- rebuild the transformed function
- reload the saved `state`
- continue at the saved `pc`

This is the closest model to notebook-style staged execution, but it still depends on explicit checkpoints and replayable state.

### 3. Full Interpreter Snapshots

This should be treated as out of scope.

Trying to restore arbitrary Python execution from a random line inside a live frame is brittle and does not match the constraints already stated in the PRD.

## Checkpoint Payload

The checkpoint record should be independent from the AST object itself.

Suggested shape:

```python
@dataclass(slots=True)
class CheckpointRecord:
    checkpoint_id: str
    script_path: str
    source_hash: str
    repair_attempt: int
    resume_kind: str          # "function" or "step"
    function_name: str
    step_id: str | None
    state_blob: bytes
    argv: list[str]
    cwd: str
```

Notes:

- `source_hash` should identify the source version that created the checkpoint.
- `resume_kind` allows the runtime to distinguish between function replay and step replay.
- `state_blob` can initially be a serialized form of `args` and `kwargs`, and later evolve into a structured state payload.
- `argv` and `cwd` help reconstruct the script execution context.

## Source Repair and Resume Order

The repair pipeline should be ordered like this:

1. run the original program
2. hit a failure
3. capture failure context and active checkpoint
4. generate a candidate repair
5. update the source file on disk
6. parse and validate the repaired source
7. compile the repaired AST
8. resolve the saved checkpoint against the repaired program
9. resume execution

This order matters.

`auto-py` should resume against the repaired source, not the original failing source. The checkpoint exists to carry state across the repair boundary.

## Runtime Resolution

Runtime resolution is the process of deciding how a saved checkpoint maps onto the repaired source file.

It should answer:

- Does the repaired file still define the checkpoint target?
- Does the saved checkpoint still belong to the same script?
- Can the saved state be safely applied to the repaired code?
- Should execution resume from a function boundary or a step boundary?

Suggested resolution flow:

1. Load the checkpoint record.
2. Read the repaired source file.
3. Parse it into an AST.
4. Validate that the checkpoint target still exists.
5. Compile the repaired AST.
6. Execute the repaired module into a fresh namespace.
7. Resolve the target function from the namespace.
8. Resume using the saved state.

In code, that means something close to:

```python
checkpoint = load_checkpoint(checkpoint_id)
prepared = prepare_module(Path(checkpoint.script_path))
namespace = build_execution_namespace(prepared.path)
exec(prepared.code, namespace, namespace)

target = namespace[checkpoint.function_name]

if checkpoint.resume_kind == "function":
    args, kwargs = deserialize_inputs(checkpoint.state_blob)
    result = target(*args, **kwargs)
else:
    state = deserialize_state(checkpoint.state_blob)
    result = target(__checkpoint=state)
```

## Matching a Checkpoint to Repaired Code

The repaired source may not be structurally identical to the original file. Runtime resolution must therefore validate the checkpoint before using it.

Recommended checks:

- script path matches
- checkpoint target function still exists
- function signature is still compatible with saved inputs
- source hash is either:
  - unchanged, or
  - explicitly marked as replaced by a repair attempt
- checkpoint version is compatible with the current runtime format

If a checkpoint cannot be resolved safely, `auto-py` should refuse to resume from it and fall back to a higher-level boundary.

## AST Instrumentation Strategy

The AST should be used to inject calls to the checkpoint runtime, not to hold checkpoint data directly.

Examples of instrumentation points:

- function entry
- before risky function calls
- after successful completion of a resumable step

For an initial implementation, function entry is enough.

Later, a `NodeTransformer` can:

- identify candidate functions
- inject `save_checkpoint(...)`
- attach stable step labels
- rewrite straight-line sections into checkpointed blocks

After any AST rewrite, location metadata should be repaired before compilation.

## Serialization Strategy

The checkpoint state should only contain serializable values.

Initial recommendation:

- use `pickle` only for local experimentation
- keep the payload narrow
- prefer explicit dictionaries over attempting to dump all locals

Recommended v1 payload:

- function name
- `args`
- `kwargs`
- simple metadata

Recommended v2 payload:

- `pc`
- selected local variables
- derived intermediate values needed for the next step

Do not attempt to serialize:

- modules
- open handles
- active exceptions
- raw frame objects
- arbitrary closures unless explicitly controlled

## Side Effects and Determinism

Checkpoint resume only makes sense if replay is acceptable.

If code performs external side effects before a failure, replaying from a checkpoint may duplicate those side effects.

Examples:

- writing to a file twice
- issuing the same API request twice
- inserting the same database record twice

The runtime should therefore treat resumability as safe only for:

- deterministic computation
- controlled internal state transitions
- idempotent side effects

This matches the PRD constraint that only deterministic execution segments are supported.

## Module Responsibilities

The current codebase already has the right high-level split.

- `runner.py`: CLI orchestration
- `validate.py`: source reading, AST parsing, AST validation, compilation
- `capture.py`: runtime execution, exception capture, execution context
- `checkpoint.py`: checkpoint model, persistence, loading, resolution, resume
- `repair.py`: candidate fix generation and source update

The important boundary is that `repair.py` updates the source file before `checkpoint.py` attempts to resume.

## Implementation Phases

### Phase 1

Implement function-entry checkpointing.

Features:

- save function inputs at entry
- on failure, repair the source file
- reload repaired module
- call the function again from the start

### Phase 2

Implement AST-assisted step checkpoints.

Features:

- inject step labels into selected functions
- save `pc + state`
- resume inside the function through a generated state machine

### Phase 3

Add compatibility checks and safer resume policies.

Features:

- signature compatibility checks
- source and repair lineage tracking
- fallback when a fine-grained checkpoint no longer matches repaired code

## Recommended First Version

The first real checkpointing system in `auto-py` should be:

- source repair first
- function-entry checkpoints only
- narrow serialized state
- resume by reloading the repaired module and replaying the function call

That is simple, extensible, and consistent with the project goals.
