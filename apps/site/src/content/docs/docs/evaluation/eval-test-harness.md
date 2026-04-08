---
title: Eval Test Harness
description: Write offline test cases in YAML and run them with fixture mode -- no LLM calls needed.
---

The eval test harness lets you define test cases directly in your workflow YAML file. Each case specifies inputs, optional fixture outputs, and expected assertions per block. Fixture mode skips all LLM calls, making tests fast, free, and deterministic.

## The eval YAML section

Add an `eval:` section at the top level of your workflow file, alongside `blocks:` and `workflow:`:

```yaml title="custom/workflows/research.yaml"
version: "1.0"
blocks:
  analyze:
    type: llm
    soul_ref: analyst
    prompt_template: "Analyze: {task_instruction}"
    assertions:
      - type: contains
        value: "analysis"

workflow:
  name: research
  entry: analyze
  transitions:
    - from: analyze
      to: null

eval:
  threshold: 0.8
  cases:
    - id: basic_research
      inputs:
        task_instruction: "Research LLMs"
      fixtures:
        analyze: "LLMs have transformed software development. This analysis covers key trends."
      expected:
        analyze:
          - type: contains
            value: "analysis"
```

## EvalSectionDef fields

The `eval:` section is parsed as an `EvalSectionDef` model:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `threshold` | `float` | no | `1.0` (when omitted) | Minimum aggregate score for the suite to pass. Range: 0.0 to 1.0 |
| `cases` | `list[EvalCaseDef]` | yes | -- | At least one test case required (`min_length=1`) |

Case IDs must be unique within the eval section. Duplicates cause a validation error.

## EvalCaseDef fields

Each entry in `cases:` is an `EvalCaseDef`:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | `str` | yes | -- | Unique identifier for this test case |
| `description` | `str` | no | `None` | Human-readable description of what this case tests |
| `inputs` | `dict[str, any]` | no | `None` | Input values passed to the executor |
| `fixtures` | `dict[str, str]` | no | `None` | Block ID to output string mapping. Skips LLM calls for these blocks |
| `expected` | `dict[str, list[dict]]` | no | `None` | Block ID to list of assertion configs. These assertions are evaluated against block outputs |

## Fixture mode

When a case provides `fixtures` that cover every block listed in `expected`, the eval runner operates in **fixture mode**:

- No executor is called (no LLM calls, no API calls)
- A `WorkflowState` is built directly from fixture strings
- Assertions run against the fixture values

This makes tests instant and free. You can run hundreds of cases without spending tokens.

```yaml title="Fixture mode -- all expected blocks have fixtures"
eval:
  cases:
    - id: fixture_only
      fixtures:
        analyze: "The LLM landscape is evolving rapidly."
        summarize: "Summary: LLMs are improving."
      expected:
        analyze:
          - type: contains
            value: "LLM"
        summarize:
          - type: starts-with
            value: "Summary"
```

If a case has `expected` blocks without matching fixtures, the runner requires an executor callback. If no executor is provided, it raises a `RuntimeError`.

## Running offline evals

When you run evals, the harness loads your workflow YAML, finds the `eval:` section, and executes each case. Fixture-only cases run instantly with no LLM calls. The result tells you whether the suite passed and gives per-case scores.

### Result types

The suite result contains:

| Field | Type | Description |
|-------|------|-------------|
| `passed` | `bool` | `True` if `score >= threshold` |
| `score` | `float` | Average of all case scores |
| `threshold` | `float` | From `eval.threshold` (defaults to `1.0` if omitted) |
| `case_results` | `list[EvalCaseResult]` | Per-case breakdown |

Each `EvalCaseResult` contains:

| Field | Type | Description |
|-------|------|-------------|
| `case_id` | `str` | Matches `id` from the YAML case |
| `passed` | `bool` | `True` if all block assertion suites passed |
| `score` | `float` | Average of block aggregate scores |
| `block_results` | `dict[str, AssertionsResult]` | Block ID to assertion results |

### Score computation

1. Each assertion produces a score (0.0 or 1.0 for deterministic types)
2. Block score = weighted average of assertion scores
3. Case score = average of block scores
4. Suite score = average of case scores
5. Suite passes if `suite_score >= threshold`

## Executor mode

For cases that need actual LLM execution (no fixtures for some blocks), the harness runs each block through the real execution pipeline. This means those cases make live LLM calls, cost tokens, and produce non-deterministic results. Use executor mode when you want to validate actual model behavior rather than testing assertion logic against known outputs.

## Mixing fixture and executor cases

A single eval section can contain both fixture-only and executor-required cases. The runner decides per-case:

```yaml title="Mixed cases"
eval:
  threshold: 0.5
  cases:
    - id: fast_fixture_test
      fixtures:
        analyze: "LLMs are powerful language models."
      expected:
        analyze:
          - type: contains
            value: "LLM"
    - id: live_execution_test
      inputs:
        task_instruction: "Research transformers"
      expected:
        analyze:
          - type: contains
            value: "transformer"
```

The fixture case runs without an executor. The live case requires one. If no executor is provided, only fixture cases succeed -- the live case raises a `RuntimeError`.

<!-- Linear: RUN-694, RUN-695, RUN-699, RUN-700 -- last verified against codebase 2026-04-07 -->
