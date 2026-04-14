# auto-py

**Autopsy failures. Apply fixes. Resume execution.**

auto-py performs an autopsy on your Python program when it crashes —  
capturing the failure, proposing a fix, validating it, and attempting recovery.

---

## What is this?

auto-py is a CLI tool that wraps Python scripts and attempts to recover from runtime failures.

When your program crashes, it:

- captures the error and execution context  
- performs a targeted “autopsy” of the failure  
- generates a candidate fix using an LLM  
- validates the fix before execution  
- retries execution from a safe checkpoint  

This is not a debugger replacement. It is an experiment in **runtime validation and recovery for AI-assisted code**.

---

## Why does this exist?

AI-assisted development speeds up writing code, but introduces uncertainty in correctness.

Traditional workflows stop at failure:

- debug  
- patch  
- rerun  

auto-py explores a different loop:

**run → fail → analyse → validate → repair → retry**

---

## Features

- Structured runtime failure capture  
- Function-level fault localisation  
- LLM-generated candidate fixes  
- Validation pipeline (syntax + execution)  
- Controlled retry from checkpoints  
- Observable repair attempts and outcomes  

---

## Installation

Recommended via pipx:

pipx install auto-py

Or locally:

pip install -e .

---

## Usage

auto-py run script.py

---

## Example

When a script crashes:

[ERROR] ZeroDivisionError at foo.py:10  

auto-py performs an autopsy:

[ATTEMPT 1]  
Analysing failure  
Generating fix  
Validating  
Re-running  

If successful:

[SUCCESS]  
Execution resumed  

---

## How it works

1. Your script runs normally  
2. On failure, auto-py captures:
   - stack trace  
   - failing function  
   - input arguments  

3. The failure is localised to a function boundary  
4. A candidate fix is generated  
5. The fix is validated:
   - must parse  
   - must execute without error  

6. The function is re-executed from a checkpoint  

---

## Design Constraints

To keep behaviour predictable and observable:

- No full program state serialization  
- No rollback of external side effects  
- Only deterministic execution segments are supported  
- Limited support for async and advanced Python features  

---

## What this is NOT

- Not a debugger  
- Not a formal verification system  
- Not guaranteed to produce correct fixes  

auto-py is a **controlled recovery system**, not a correctness guarantee.

---

## Project Structure

src/

- runner.py — CLI entrypoint  
- capture.py — failure and context extraction  
- checkpoint.py — controlled re-execution  
- validate.py — validation pipeline  
- repair.py — LLM interaction  
- llm/ — local-first LLM gateway interfaces  
- repair_agent/ — checkpoint-aware repair loop scaffold  

examples/

- failing scripts for testing  

docs/

- PRD.md — product requirements  
- CHECKPOINTING.md — checkpointing and resume design  
- REPAIR_AGENT_PRD.md — repair agent scope and roadmap  

---

## Local Model Gateway

The repair agent scaffold is designed around local/self-hosted models first.

Default environment:

```text
AUTO_PY_LLM_BASE_URL=http://localhost:11434/v1
AUTO_PY_LLM_MODEL=qwen2.5-coder:7b
AUTO_PY_LLM_API_KEY=
```

For `pipx` installs, create a user-level config file:

```bash
auto-py llm-config init
auto-py llm-config path
auto-py llm-config show
```

On macOS, the default config path is:

```text
~/Library/Application Support/auto-py/config.toml
```

The gateway uses the OpenAI-compatible chat completions shape so it can point at
local runtimes such as Ollama, LM Studio, Docker Model Runner, or llama.cpp
server without changing the repair loop.

---

## Roadmap

- Stronger validation beyond “no crash”  
- Multiple candidate fix comparison  
- Lightweight invariant checks  
- Interactive repair mode  

---

## Limitations

- Cannot reliably resume mid-loop execution  
- Does not handle external side effects (files, network)  
- May produce incorrect but runnable fixes  

---

## Why this matters

This project explores a shift in software engineering:

From:
- write → test → fix  

To:
- run → fail → analyse → validate → repair → retry  

---

## Contributing

This is an experimental system focused on runtime behaviour and validation.

Contributions that improve:
- validation quality  
- observability  
- repair strategies  

are welcome.

---

## License

TBD
auto-py run script.py
