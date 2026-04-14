# Repair Agent PRD

## 1. Purpose

Build a lightweight, checkpoint-aware repair agent for `auto-py`.

The agent receives structured runtime failure context, asks a local-first LLM
gateway for a minimal patch, runs deterministic validation, and returns only
validated repairs for application and checkpoint resume.

The agent is not intended to become a general autonomous coding assistant. It is
a bounded repair subsystem for Python runtime failures.

## 2. Product Position

`auto-py` owns execution, checkpoint capture, validation, patch policy, and
resume decisions.

The repair agent owns patch proposal and retry coordination.

The LLM owns no authority. It proposes text. `auto-py` decides whether that text
is acceptable.

## 3. Primary Goals

- Support local/self-hosted models as the first-class path.
- Keep provider swapping possible through a lightweight LLM gateway.
- Provide a narrow repair loop: failure context -> patch -> validation feedback
  -> revised patch.
- Preserve checkpoint compatibility before resuming.
- Keep final validation deterministic and independent of model claims.

## 4. Non-Goals

- General-purpose coding agent framework.
- Arbitrary shell access for the LLM.
- Multi-agent orchestration.
- Full repository refactoring.
- Formal correctness guarantees.
- Trusting model-reported validation.

## 5. User Flow

```text
auto-py run script.py --repair
  -> script executes
  -> runtime failure occurs
  -> failure context and latest checkpoint are captured
  -> repair agent proposes a unified diff
  -> patch is applied to a temporary candidate workspace
  -> deterministic validation runs
  -> invalid result is fed back into the model
  -> valid result is revalidated from a clean candidate
  -> patch is applied to the real source
  -> execution resumes from the checkpoint when safe
```

## 6. Local-First LLM Gateway

The default gateway should target OpenAI-compatible local model servers.

Default local config:

```text
AUTO_PY_LLM_BASE_URL=http://localhost:11434/v1
AUTO_PY_LLM_MODEL=qwen2.5-coder:7b
AUTO_PY_LLM_API_KEY=
```

For `pipx` installs, the package should not rely on repository-local config.
It should use a user-level config file plus environment overrides.

Default config paths:

- macOS: `~/Library/Application Support/auto-py/config.toml`
- Linux: `$XDG_CONFIG_HOME/auto-py/config.toml` or `~/.config/auto-py/config.toml`
- Windows: `%APPDATA%/auto-py/config.toml`

Config file shape:

```toml
[llm]
provider = "openai-compatible"
base_url = "http://localhost:11434/v1"
model = "qwen2.5-coder:7b"
api_key_env = "AUTO_PY_LLM_API_KEY"
timeout_seconds = 120
```

Initial CLI helper:

```bash
auto-py llm-config init
auto-py llm-config path
auto-py llm-config show
```

Supported first-class local runtimes should include:

- Ollama
- LM Studio
- Docker Model Runner
- llama.cpp server

Cloud gateways or hosted providers can be added by changing configuration, not
by changing repair-agent code.

Example future CLI:

```bash
auto-py run main.py --repair \
  --llm-base-url http://localhost:11434/v1 \
  --llm-model qwen2.5-coder:7b
```

## 7. Gateway Contract

The repair loop depends only on:

```python
class LLMGateway(Protocol):
    def complete(self, request: LLMRequest) -> LLMResponse:
        ...
```

Provider-specific details are isolated behind gateway implementations.

Initial implementation:

- `OpenAICompatibleGateway`

Potential future implementations:

- `PortkeyGateway`
- `MockGateway`
- `RecordedGateway`
- direct provider SDK gateways if needed

## 8. Repair Context

The agent should receive a structured failure packet:

- script path
- exception type
- exception message
- traceback text
- failing line
- failing function
- source snippet
- checkpoint summary
- safe summaries of selected locals/globals
- previous validation feedback

The agent should not receive raw pickle checkpoint blobs.

## 9. Patch Output Contract

The model must return a unified diff only.

Rules:

- Modify the smallest relevant code region.
- Preserve checkpoint calls and checkpoint comments.
- Avoid unrelated formatting churn.
- Avoid broad rewrites unless validation feedback requires it.
- Do not claim tests or validation passed.

## 10. Validation Ladder

Each candidate patch should be validated in a temporary workspace.

Initial deterministic validators:

- patch parses as a unified diff
- patch applies cleanly
- repaired source parses with `ast.parse`
- repaired source compiles
- checkpoint can still be resolved

Future validators:

- run project tests
- run the failing script in a subprocess
- compare stdout/stderr where deterministic
- reject suspicious imports or unsafe calls
- check required locals after checkpoint
- lint/format checks

## 11. Final Validation

Before changing the real source, `auto-py` must rerun validation from a clean
candidate workspace.

The final pass should not trust:

- model claims
- previous intermediate validation results
- cached candidate state

Only after final validation passes may `auto-py` apply the patch and attempt
checkpoint resume.

## 12. Checkpoint Compatibility Requirements

Before resume, the repaired source must satisfy:

- target script still exists
- target function still exists
- checkpoint label or resolved checkpoint site still exists
- checkpoint remains inside the expected function
- required post-checkpoint locals are restorable
- resume kind is supported

If compatibility fails, the system should either retry repair, fall back to a
coarser replay boundary, or stop without resuming.

## 13. Safety Boundary

The model can propose:

- source patches
- explanations for why a patch may fix the failure

The model cannot directly:

- write the real source
- run arbitrary commands
- mark validation as successful
- force checkpoint resume

`auto-py` remains the authority for all side effects.

## 14. Milestones

### Milestone 1: Scaffold

- Add repair-agent package
- Add local-first LLM gateway interface
- Add prompt builder
- Add retry loop around patch proposals
- Add PRD and architecture notes

### Milestone 2: Candidate Patch Validation

- Apply unified diffs to temp workspaces
- Parse/compile repaired candidates
- Feed validation failures back to the model
- Add deterministic mock backend tests

### Milestone 3: Checkpoint-Aware Resume Validation

- Validate function name match
- Validate checkpoint label/site match
- Validate required locals
- Refuse unsafe resume

### Milestone 4: Local Model Integration

- Test with Ollama
- Test with LM Studio
- Test with Docker Model Runner
- Document recommended local model settings for Apple Silicon

### Milestone 5: Evaluation

- Add reproducible failing examples
- Measure repair success rate
- Measure retry count
- Measure checkpoint resume success
- Compare local model and hosted gateway behavior

## 15. Open Questions

- Should the agent be allowed to patch only the failing script at first?
- How should checkpoint sites be matched after the source changes?
- Should failed local model attempts fall back to a hosted gateway?
- What is the minimum useful source context for small local models?
- Should model prompts include full function source or line-window snippets?

## 16. Current Scaffold

Current files:

- `src/auto_py/llm/gateway.py`
- `src/auto_py/llm/openai_compatible.py`
- `src/auto_py/repair_agent/context.py`
- `src/auto_py/repair_agent/prompts.py`
- `src/auto_py/repair_agent/loop.py`
- `src/auto_py/repair_agent/result.py`

The scaffold deliberately stops before patch application and command execution.
Those are the next pieces to add once the validation boundary is designed.
