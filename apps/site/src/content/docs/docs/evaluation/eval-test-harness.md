---
title: Eval Test Harness
description: Write offline test cases in YAML and run them with fixture mode -- no LLM calls needed.
---

The eval test harness lets you define test cases directly in your workflow YAML file. Each case specifies inputs, optional fixture outputs, and expected assertions per block. Fixture mode skips all LLM calls, making tests fast, free, and deterministic.

## The eval YAML section

Add an `eval:` section at the top level of your workflow file, alongside `blocks:` and `workflow:`:

```yaml title="custom/workflows/research.yaml"
version: "1.0"
id: research
kind: workflow
blocks:
  analyze:
    type: code
    code: |
      def main(data):
          return "unused in fixture mode"
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
| `threshold` | `float` | no | `None` in the schema, treated as `1.0` at runtime when omitted | Minimum aggregate score for the suite to pass. Range: 0.0 to 1.0 |
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

:::note
Custom assertions are supported in `expected` just like built-in assertions, but scanner-based auto-discovery only happens when `run_eval()` is given a workflow file path. Passing raw YAML text does not scan `custom/assertions`.
:::

## Running offline evals

When you run evals, the harness loads your workflow YAML, finds the `eval:` section, and executes each case. Fixture-only cases run instantly with no LLM calls. The result tells you whether the suite passed and gives per-case scores.

### Result types

The suite result contains:

| Field | Type | Description |
|-------|------|-------------|
| `passed` | `bool` | `True` if `score >= threshold` |
| `score` | `float` | Average of all case scores |
| `threshold` | `float` | From `eval.threshold`, or `1.0` at runtime when the field is omitted |
| `case_results` | `list[EvalCaseResult]` | Per-case breakdown |

Each `EvalCaseResult` contains:

| Field | Type | Description |
|-------|------|-------------|
| `case_id` | `str` | Matches `id` from the YAML case |
| `passed` | `bool` | `True` if all block assertion suites passed |
| `score` | `float` | Average of block aggregate scores |
| `block_results` | `dict[str, AssertionsResult]` | Block ID to assertion results |

### Score computation

1. Each assertion produces a score between `0.0` and `1.0`
2. Block score = weighted average of assertion scores
3. Case score = average of block scores
4. Suite score = average of case scores
5. Suite passes if `suite_score >= threshold`

## Executor mode

For cases that need live execution (no fixtures for some blocks), `run_eval()` awaits a caller-supplied `executor(raw, inputs)` function that must return a `WorkflowState`. That executor can call the real workflow runtime, a test double, or any other harness you provide. `run_eval()` itself does not automatically run the full execution pipeline.

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

The fixture case runs without an executor. The live case requires one. If no executor is provided, `run_eval()` raises a `RuntimeError` when it reaches the first executor-required case; it does not return partial suite results.

<!-- Linear: RUN-694, RUN-695, RUN-699, RUN-700, RUN-769, RUN-800, RUN-801 -- last verified against codebase 2026-04-10 -->
