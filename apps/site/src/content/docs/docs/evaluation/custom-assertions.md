---
title: Custom Assertions
description: Create project-local Python assertions under custom/assertions and use them in offline evals and live workflow runs.
---

Custom assertions let you add workspace-local checks alongside Runsight's 15 built-in assertions. The Python contract is **promptfoo-compatible** — if you already have promptfoo assertion functions, they work in Runsight with minimal changes. Add a YAML manifest, drop your Python file next to it, and reference it as `custom:<name>` in your workflow.

Runsight discovers custom assertions from `custom/assertions/*.yaml`, registers each one under `custom:{file_stem}`, and runs them in both offline evals and live API workflow runs.

For built-in assertion types and shared assertion config fields, see [Assertions](/docs/evaluation/assertions).

## Quick Start

This example creates a custom assertion named `tone_check`, then uses it in an offline eval case with a built-in assertion alongside it.

```yaml title="custom/assertions/tone_check.yaml"
version: "1.0"
name: "Tone Check"
description: "Passes when output starts with a configured prefix."
returns: "grading_result"
source: "tone_check.py"
params:
  type: object
  properties:
    prefix:
      type: string
  required: ["prefix"]
```

```python title="custom/assertions/tone_check.py"
def get_assert(output, context):
    config = context.get("config", {})
    return {
        "pass": output.startswith(config.get("prefix", "")),
        "score": 0.9,
        "reason": f"prefix={config.get('prefix', '')}",
    }
```

```yaml title="custom/workflows/custom-assertions-demo.yaml"
version: "1.0"
config:
  model_name: gpt-4o
blocks:
  analyze:
    type: code
    code: |
      def main(data):
          return "unused in fixture mode"
workflow:
  name: custom_assertions_demo
  entry: analyze
  transitions:
    - from: analyze
      to: null
eval:
  threshold: 0.5
  cases:
    - id: tone_case
      fixtures:
        analyze: "calm response"
      expected:
        analyze:
          - type: custom:tone_check
            config:
              prefix: calm
          - type: contains
            value: "response"
```

What this does:

- The assertion's canonical ID is `tone_check` because the manifest file is `tone_check.yaml`.
- The runtime type is `custom:tone_check`.
- The `config` object is validated against `params` before the plugin runs.
- The same custom assertion can also be used under a block's normal `assertions:` list during API workflow runs.

:::note
Custom assertion discovery requires a workflow file on disk — the scanner reads your project's `custom/assertions/` directory relative to the workflow file path. If you pass raw YAML strings programmatically instead of file paths, custom assertions won't be discovered automatically.
:::

## YAML Manifest Reference

Each custom assertion is defined by a YAML manifest in `custom/assertions/<id>.yaml`.

```yaml title="custom/assertions/example.yaml"
version: "1.0"
name: "Example Assertion"
description: "Checks something about the block output."
returns: "bool"
source: "example.py"
params:
  type: object
  properties:
    enabled:
      type: boolean
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | `string` | yes | Manifest version string |
| `name` | `string` | yes | Display name for humans. This is not the runtime ID |
| `description` | `string` | yes | Short description of the assertion |
| `returns` | `"bool"` or `"grading_result"` | yes | Declares the plugin return contract |
| `source` | `string` | yes | Python file to load, relative to the manifest file |
| `params` | JSON Schema object | no | Schema used to validate the assertion's `config` before plugin execution |

Important details:

- The canonical runtime ID is the file stem, not `name`.
- `custom/assertions/tone_check.yaml` always registers as `custom:tone_check`.
- Extra top-level manifest fields are rejected.
- Built-in assertion name collisions are rejected at scan time.
- The source file must exist relative to the manifest file.

## Python Contract

A custom assertion source file must define exactly this function:

```python title="custom/assertions/example.py"
def get_assert(output, context):
    return True
```

Rules:

- The function name must be `get_assert`.
- The parameter list must be exactly `(output, context)`.
- The function must be synchronous.
- Runsight validates the function contract before registration.
- The plugin runs in a separate subprocess with a minimal environment.
- Plugin execution times out after 30 seconds.

The plugin receives:

- `output`: the block output string being checked
- `context`: a plain Python dict with assertion metadata and per-assertion config

Runsight does not forward API keys into the plugin subprocess environment.

## Return Types

The manifest `returns` field controls how Runsight interprets the plugin result.

### `bool`

Use `returns: "bool"` when the assertion is a simple pass/fail check.

```python title="custom/assertions/contains_calm.py"
def get_assert(output, context):
    return "calm" in output
```

`True` becomes a passing result with score `1.0`. `False` becomes a failing result with score `0.0`.

### `grading_result`

Use `returns: "grading_result"` when you need to control the score or reason.

```python title="custom/assertions/tone_check.py"
def get_assert(output, context):
    config = context.get("config", {})
    return {
        "pass": output.startswith(config.get("prefix", "")),
        "score": 0.9,
        "reason": f"prefix={config.get('prefix', '')}",
    }
```

Accepted fields:

| Field | Required | Notes |
|-------|----------|-------|
| `passed` or `pass_` or `pass` | yes | Runsight accepts these aliases in that precedence |
| `score` | yes | Must be numeric and between `0.0` and `1.0` |
| `reason` | no | Optional. Non-string values are coerced with `str()` |

Notes:

- `score` may be an `int` or `float`; Runsight converts it to `float`.
- If the returned shape does not match the declared contract, the assertion fails with a runtime error message instead of crashing the run.

## Config & Params

Each assertion entry in workflow YAML can include a `config` field:

```yaml title="Block assertion config"
assertions:
  - type: custom:tone_check
    config:
      prefix: calm
```

For custom assertions, Runsight passes that value through two stages:

1. If the manifest defines `params`, Runsight validates `config` against that JSON Schema.
2. If validation succeeds, the exact value is exposed to the plugin as `context["config"]`.

If the manifest does not define `params`, Runsight skips config validation.

:::note
Custom plugins receive their per-assertion input through `config`. The generic `value` and `threshold` fields still exist on assertion objects, but Runsight does not inject them into the plugin context dict.
:::

### Schema-validated config

```yaml title="custom/assertions/budget_guard.yaml"
version: "1.0"
name: "Budget Guard"
description: "Requires a numeric budget."
returns: "bool"
source: "budget_guard.py"
params:
  type: object
  properties:
    budget:
      type: number
  required: ["budget"]
```

```python title="custom/assertions/budget_guard.py"
def get_assert(output, context):
    return True
```

```yaml title="Workflow usage"
assertions:
  - type: custom:budget_guard
    config:
      budget: 0.05
```

If `config` is invalid, Runsight returns a failing result whose reason starts with `Config validation failed:` and skips plugin execution.

### Generic assertion features still work

Custom assertions use the same outer assertion config object as built-ins, so these features still apply:

- `weight`
- `metric`
- `transform`
- `not-` negation, for example `not-custom:blocked_word`

## Context Dict Reference

Custom assertions receive a plain dict, not an `AssertionContext` object.

| Key | Type | Description |
|-----|------|-------------|
| `vars` | `dict` | Workflow variables for the assertion context |
| `config` | `any` | The per-assertion `config` value from workflow YAML |
| `prompt` | `string` | Prompt text in the current assertion context |
| `prompt_hash` | `string` | Prompt hash for the current run |
| `soul_id` | `string` | Soul ID for the block being evaluated |
| `soul_version` | `string` | Soul version hash or identifier |
| `block_id` | `string` | Block ID |
| `block_type` | `string` | Block type |
| `cost_usd` | `float` | Execution cost in USD |
| `total_tokens` | `int` | Total tokens used |
| `latency_ms` | `float` | Block latency in milliseconds |
| `run_id` | `string` | Run ID |
| `workflow_id` | `string` | Workflow identifier from the current assertion context. In live API runs this is currently the workflow name; offline eval uses an empty string |

Notes:

- The key is `vars`, not `variables`.
- The key is `config`, even when the config value is `None`.
- Offline eval populates most context fields with empty strings or zeros.
- Live API execution fills prompt, soul, cost, token, latency, run, and workflow fields from the run context.

## Migrating from Promptfoo

Runsight's custom assertion contract is intentionally close to promptfoo-style Python assertions.

A promptfoo-style function body like this works unchanged:

```python title="custom/assertions/tone_check.py"
def get_assert(output, context):
    config = context.get("config", {})
    return {
        "pass": output.startswith(config.get("prefix", "")),
        "score": 0.9,
        "reason": f"prefix={config.get('prefix', '')}",
    }
```

The main Runsight-specific additions are:

1. Put the code in `custom/assertions/<id>.py`
2. Add a matching manifest in `custom/assertions/<id>.yaml`
3. Reference it in workflow YAML as `custom:<id>`

Example:

```yaml title="Workflow assertion entry"
assertions:
  - type: custom:tone_check
    config:
      prefix: calm
```

Remember that `tone_check` comes from the filename, not the manifest `name`.

## Limitations

Current custom assertion support is intentionally narrow:

- Discovery only looks for YAML manifests in `custom/assertions/*.yaml`.
- The Python contract is only `def get_assert(output, context)`.
- Supported return contracts are only `bool` and `grading_result`.
- Manifest fields are fixed to `version`, `name`, `description`, `returns`, `source`, and optional `params`.
- Plugins run in a separate subprocess with a minimal environment and a 30 second timeout.
- API keys are not forwarded into that subprocess environment.
- Offline eval auto-discovers custom assertions only from workflow file paths, not raw YAML strings.
- This feature documents local Python assertions only. LLM-calling plugins are not supported today because Runsight does not forward API keys into the plugin subprocess.

See [RUN-306](https://linear.app/runsight/issue/RUN-306/batch-eval-llm-graded-assertions-defensive-red-team) for future LLM-graded assertion work.

## Error Messages

These are the most common failure modes you will see.

### Manifest and discovery errors

These happen before the assertion is registered:

- Missing or invalid required manifest fields
- Unsupported extra manifest fields
- Invalid `returns` value
- Built-in ID collision such as `contains.yaml`
- Invalid Python signature such as anything other than `def get_assert(output, context)`

### Runtime assertion errors

These return failing results instead of crashing the run:

- `Config validation failed: ...`
- `Custom assertion 'name' failed: plugin exploded`
- `Custom assertion 'name' declares returns: bool but get_assert returned 'dict'`
- `custom assertion plugin timed out after 30s`

### What happens on failure

In both offline eval and live API execution:

- The assertion result is recorded as failed
- The run continues
- Other assertions on the same block still produce their own results
- Live API runs still persist `eval_score`, `eval_passed`, and `eval_results`, and still emit `node_eval_complete` SSE events

<!-- Linear: RUN-769, RUN-794, RUN-795, RUN-796, RUN-797, RUN-798, RUN-799, RUN-800, RUN-801 -- last verified against codebase 2026-04-10 -->
