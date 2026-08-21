# Agentic Modeling Sandbox (AMS)

AMS is an **LLM-free environment/control plane** for agent-built modeling programs.

The external coding agent owns reasoning, decomposition, architecture, code generation, repair, and refactoring. AMS owns the environment: state, available capabilities, hard constraints, validation rules, evaluation protocol, and structured feedback.

## V0.1 boundary

Two fixed-schema manifests are used:

- `environment.yaml` — environment-owner controlled: objective, capabilities, hard constraints, datasets, reward/evaluation criteria.
- `candidate.yaml` — agent generated: proposed decomposition, LLM boundaries, contracts, validations, metrics, optimization targets, and artifact locations.

The candidate schema intentionally forbids environment fields such as hard constraints or acceptance thresholds.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e . pytest

ams init demo
ams state demo --json
ams rules demo --json
ams capabilities demo --json
ams validate demo --json
```

Run tests:

```bash
pytest
```

## Current scope

V0.1 implements:

- fixed Pydantic schemas;
- environment/candidate separation;
- YAML loading and strict validation;
- agent-oriented JSON CLI output;
- initial decomposition/evaluation enforcement;
- pension-ALM example environment template;
- tests proving the candidate cannot override environment-controlled fields.

No LLM SDK is a dependency of the AMS core.

## V0.2 action → execution → observation loop

AMS now exposes a deterministic action interface. An external agent submits typed JSON actions; AMS applies workspace/execution policy, executes allowed actions, and returns a structured observation. Every observation is persisted in `.ams/history.jsonl`.

Supported actions:

- `write_file` — writes only under environment-approved roots and enforces file-size limits.
- `read_file` — reads files only from inside the workspace and limits returned content.
- `run_command` — executes `argv` without a shell, using an environment-defined executable allowlist, timeout, and output limit.
- `run_tests` — same execution path, with a test-oriented default command.

Example:

```json
{
  "type": "write_file",
  "path": "src/model.py",
  "content": "def funded_ratio(assets, liabilities):\n    return assets / liabilities\n"
}
```

```bash
ams act demo action.json --json
ams observations demo --json
```

Or from stdin:

```bash
printf '%s' '{"type":"run_command","argv":["python","-c","print(2+3)"]}' \
  | ams act demo - --json
```

The local V0.2 runner enforces path boundaries, command allowlists, timeouts, file sizes, and output limits.

Two limits of the local subprocess backend are worth stating precisely:

- `network: false` is recorded in observations but is **not OS-enforced**.
- an allowlisted interpreter (`python`) can write anywhere the AMS process can, so `allowed_write_paths` cannot be *prevented* at the OS level. AMS instead detects and reverts such writes for environment-owned files inside the workspace — see [v0.9](#v09--environment-integrity-held-out-budget-and-executable-checks). Writes elsewhere on the host filesystem remain uncontained.

A later isolated backend (container/VM or equivalent) should enforce network and stronger process/filesystem isolation without changing the action/observation protocol.

## v0.3 — Typed modeling capabilities

AMS now supports environment-owned deterministic modeling capabilities. The external agent can discover them with:

```bash
ams capabilities ./workspace --json
```

and invoke only manifest-declared capabilities through the same action/observation protocol:

```json
{
  "type": "invoke_capability",
  "capability": "calculate_funded_ratio",
  "arguments": {
    "asset_value": 90.0,
    "liability_value": 100.0
  }
}
```

The corresponding CLI call is:

```bash
ams act ./workspace action.json --json
```

A successful observation contains the exact declared callable, deterministic flag, arguments, result, elapsed time, and policy decision.

The starter `pension-alm` environment now owns these capabilities under `tools/`:

- `project_liabilities`
- `value_assets`
- `shock_assets`
- `apply_scenario`
- `calculate_funded_ratio`
- `reconcile_funded_ratio`

`tools/` is intentionally not in the default agent-writable roots. The environment defines the world; the external agent composes the available capabilities without silently changing the primitives it is evaluated against.

### Capability boundary

The calling agent cannot pass an arbitrary import path to the runtime. It provides a capability name, AMS resolves that name against `environment.yaml`, loads the environment-declared callable, validates the arguments against the Python signature, executes it, and requires a JSON-serializable result.

```text
External agent
    |
    | invoke_capability(name, arguments)
    v
AMS capability registry
    |
    | declared name -> environment-owned callable
    v
Signature validation
    |
    v
Deterministic modeling function
    |
    v
Structured observation + history
```

This is the first point where AMS becomes a modeling environment rather than only a controlled coding workspace.

## v0.4 — Evaluation / Reward

AMS now includes a deterministic evaluation layer.

Candidate projects declare an evaluation entrypoint in `candidate.yaml`:

```yaml
artifacts:
  source_roots: [src]
  test_roots: [tests]
  entrypoint: src/model.py:predict
```

The environment owns the dataset locations, metric names, acceptance threshold, and held-out split policy.

```bash
ams eval . --split validation --json
```

The external agent receives structured fitness feedback, including aggregate score, acceptance threshold, metric names, and case-level results for train/validation splits.

Protected held-out evaluation requires an explicit final operation:

```bash
ams eval . --split test --final --json
```

For a protected test split, AMS returns only aggregate fitness and hides individual case details.

The same operation is available through the action protocol:

```json
{
  "type": "evaluate_candidate",
  "split": "validation",
  "final": false
}
```

This keeps the responsibility split intact:

```text
External agent  -> builds / modifies candidate
AMS             -> evaluates under environment-owned rules
Observation     -> fitness + validation evidence
External agent  -> chooses its next action
```


## v0.5 — DSPy source inspection

AMS can now inspect candidate Python source with the standard-library AST without importing or executing it.

```bash
ams inspect-dspy . --json
ams validate . --source --json
```

The inspector discovers common DSPy LM boundaries (`Predict`, `ChainOfThought`, `ReAct`, `RLM`, `CodeAct`, `ProgramOfThought`) and `dspy.Signature` classes. Source-aware validation compares the discovered program with the agent-owned `candidate.yaml`.

It enforces properties rather than architecture:

- every discovered material DSPy boundary must be declared;
- every declared LLM boundary must exist in source;
- declared and implemented DSPy module types must agree;
- discovered signatures should expose explicit input/output fields;
- modules marked as optimization targets must appear in the candidate optimization declaration.

AMS still does **not** decide which DSPy modules the agent should create.


## v0.6 — Optimization protocol

AMS now issues an optimization protocol without performing LLM optimization itself:

```bash
ams optimization-plan . --json
```

The plan identifies independently optimizable DSPy boundaries, records the validation baseline, fingerprints train/validation/test datasets, and protects the held-out split. The external agent or DSPy runtime performs the actual optimization.

After the external optimizer modifies the candidate:

```bash
ams verify-optimization . --json
```

AMS verifies dataset integrity, source/contracts, validation improvement, and aggregate held-out performance. Individual protected test cases remain hidden.

This preserves the core boundary: **the external agent optimizes; AMS defines and verifies the environment and evidence.**


## v0.7 — Self-describing CLI and agent discovery

Before adding MCP, AMS now exposes a complete discovery protocol through the CLI.

```bash
ams --help
ams help --json
ams help decomposition --json
ams schema candidate --json
ams schema action --json
ams examples workflow --json
ams guide . --json
ams test . --json
```

### Concept help

`ams help <topic>` explains environment, candidate ownership, actions, decomposition, contracts, evaluation, optimization, and DSPy behavior. Decomposition examples are explicitly non-prescriptive.

### Fixed schema introspection

`ams schema <artifact>` exposes the actual fixed Pydantic JSON schemas where available, including environment, candidate, action, observation, and validation protocols. Evaluation and optimization-plan protocols also expose stable schema descriptions.

### Deterministic guide

`ams guide` inspects current workspace state and returns the next unmet environment requirement. It never uses an LLM and never proposes the candidate modeling architecture.

Typical progression:

```text
uninitialized
  -> candidate manifest
  -> candidate contract
  -> source alignment
  -> validation evaluation
  -> optimization baseline
  -> external optimization
```

This allows an unfamiliar coding agent to discover how to operate AMS without a preloaded AMS-specific system prompt.

## v0.8 — Observability and reporting

```bash
ams summary . --json
ams report .
ams report . --output ams-report.md
```

The observability summary covers action/status counts, policy failures, source alignment, current validation fitness, evaluation score history, recent failures, and optimization state. `ams report` renders this evidence as Markdown.

A real external-LLM loop is documented in `examples/external-llm-agent-loop.md`: a deliberately bad candidate scored 0.35, AMS returned structured feedback, the external LLM repaired it, and the candidate then scored 1.00 and passed tests.

## v0.9 — Environment integrity, held-out budget, and executable checks

v0.9 closes gaps where the environment *declared* a rule it did not actually enforce.

### Evaluation is always recorded

`ams eval` now runs through the action/observation protocol, so direct CLI evaluations appear in `.ams/history.jsonl` and in `ams report` score trends. Output shape and exit codes are unchanged (`0` accepted, `1` rejected, `2` protocol error).

### Candidate workspace on the test path

`run_command` and `run_tests` receive the workspace root on `PYTHONPATH`, so candidate tests can import the candidate's own source roots (`from src.model import ...`).

### Environment integrity

Files the agent may not write — `environment.yaml`, `tools/`, `evals/`, `.ams/` — are snapshotted before every subprocess and restored afterwards. A command that changes them returns a denied observation:

```json
{
  "status": "denied",
  "policy": {"rule": "ENVIRONMENT_INTEGRITY"},
  "data": {"restored_paths": ["tools/recon.py"]}
}
```

This means the agent cannot silently rewrite the primitives it is evaluated against, lower its own acceptance threshold, or edit the datasets — even through an allowlisted interpreter. Transient artifacts (`__pycache__`, `.pytest_cache`) are ignored, so ordinary test runs are unaffected.

### Protected held-out budget

The environment caps how often the protected split may be scored, so its aggregate cannot be used as a tuning signal:

```yaml
evaluation:
  protect_test_split: true
  max_final_evaluations: 3   # null for unlimited
```

Each `--final` evaluation is recorded in `.ams/heldout-access.json` and the remaining budget is returned with the report. Exhausting it yields a denied observation. The ledger is environment-owned, so it is covered by the integrity check above. **Existing environments inherit the default of 3**; set it to `null` to restore unlimited access.

### Executable validation checks

Previously `validation_compliance` was scored from a `validation_passed` field the candidate produced about itself, and `required_checks` were only string-matched against `candidate.yaml`. The environment can now declare checks that AMS executes:

```yaml
constraints:
  validation:
    required_checks: [funded_ratio_reconciles]
    executable_checks:
      funded_ratio_reconciles: tools.funding:check_reconciles
```

Each check is called as `fn(inputs, output)` and returns a bool or a dict with a `passed` key. Results appear per case:

```json
{"id": "val-underfunded", "checks": {"funded_ratio_reconciles": false}}
```

When an environment declares executable checks they are authoritative and the candidate's self-report is ignored. A candidate returning a wrong funded ratio while reporting `validation_passed: true` scores 0.93 (accepted) under self-reporting and 0.60 (rejected) under an executable check. Environments that declare no `executable_checks` keep the previous behaviour.
