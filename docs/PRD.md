Runtime Repair CLI — Product Requirements Document (PRD)
1. Overview
Purpose

Build a CLI tool that intercepts runtime errors in Python programs, generates candidate fixes using an LLM, validates those fixes, and attempts controlled re-execution from a defined checkpoint.

The system is designed to explore runtime validation and recovery, not to guarantee full program correctness.

2. Problem Statement

Modern development increasingly relies on AI-generated code, which introduces uncertainty in correctness.

Traditional workflows rely on:

manual debugging
test-driven validation

These approaches:

do not assist at runtime
assume developer intervention

This tool investigates:

Can runtime failures be partially recovered automatically using constrained validation and repair?

3. Goals and Non-Goals
Goals
Capture runtime failures with structured context
Localise failure to a constrained code region
Generate candidate fixes using an LLM
Validate fixes before execution
Retry execution from a controlled checkpoint
Provide observable metrics on repair behaviour
Non-Goals
Full program correctness guarantees
Complete execution state serialization
Support for all Python constructs (e.g., async, generators)
Handling non-deterministic or side-effect-heavy programs
4. Core Concepts
4.1 Failure Capture

When an exception occurs:

Capture stack trace
Identify file, function, and line
Extract relevant execution context (arguments, limited locals)
4.2 Fault Localisation
Identify the failing function or code region
Use this region as the scope for repair
4.3 Checkpointing (Controlled Re-execution)
Checkpoint is defined as a function-level boundary
Capture only input arguments and minimal context
No full state serialization
Recovery is performed via controlled re-execution
4.4 Repair Loop
Failure occurs
Context is captured
LLM generates candidate fix
Fix is validated
If valid, apply patch
Re-execute from checkpoint
Retry up to a fixed limit (default: 3 attempts)
4.5 Validation

Two layers of validation are applied:

Syntactic validation:

Parse generated code using AST
Reject invalid Python before execution

Runtime validation:

Ensure code executes without raising an exception
5. User Experience
CLI Usage

auto-py script.py

Expected Behaviour
Script runs normally
On failure:
structured error is displayed
repair loop is triggered
outcome is reported
Example Output

[ERROR] ZeroDivisionError at foo.py:10

[ATTEMPT 1]
Generated fix
Validation passed
Re-running

[SUCCESS]
Execution resumed successfully

6. System Architecture
Components
runner.py
CLI entrypoint and orchestration
capture.py
Error and context extraction
checkpoint.py
Execution boundary reconstruction
validate.py
Syntax and runtime validation
repair.py
LLM interaction
Data Flow

Execution → Failure → Capture → Localise → Generate Fix → Validate → Apply → Re-run

7. Data Structures
Failure Context
error: exception type
file: source file
line: line number
function: function name
args: input arguments
kwargs: keyword arguments
locals: filtered local variables
Logical Call Stack (Optional)
ordered list of function calls leading to failure
8. Success Criteria
Runtime Reasoning
Capture and inspect execution context across at least 3 failure scenarios
Accurately identify failure location
Validation Design
Reject syntactically invalid fixes before execution
Demonstrate at least one behavioural validation condition
AI-Assisted Repair
Demonstrate at least one successful repair cycle
Show improvement with retries over single attempt
Execution Control and Recovery
Implement function-level checkpointing
Successfully resume execution from checkpoint
9. Constraints
Only deterministic execution segments supported
No rollback of external side effects
Limited support for complex Python features
10. Risks

Incorrect fix applied
→ mitigated by validation and retry limits

Infinite repair loop
→ mitigated by max attempt threshold

Poor LLM output
→ mitigated by constrained input and validation

State inconsistency
→ mitigated by function-level checkpointing

11. Milestones
Week 1: failure capture
Week 2: localisation and checkpointing
Week 3: validation pipeline
Week 4: repair loop
Week 5+: evaluation and refinement
12. Future Extensions
Multiple candidate comparison
Invariant-based validation
Interactive repair mode
Improved checkpoint granularity
13. Out of Scope
Full debugger functionality
Formal verification
Production-grade guarantees
14. Definition of Done

The project is complete when:

CLI executes and captures failures
At least one repair cycle succeeds
Validation rejects invalid fixes
Execution resumes from checkpoint
Behaviour is documented and reproducible