---
title: YAML Schema
description: Structure of a Runsight workflow YAML file — all top-level sections and their fields.
---

A Runsight workflow is a YAML file with a defined schema. The engine validates every file against Pydantic models before parsing. A JSON schema is auto-generated for Monaco editor autocomplete.

## File structure

```yaml
version: "1.0"

souls:                    # optional — inline soul definitions
  my_soul:
    id: my_soul
    role: Analyst
    system_prompt: "..."
    model_name: gpt-4.1-mini

tools: [delegate, http]   # optional — tool IDs available to this workflow

blocks:
  step_one:
    type: linear
    soul_ref: my_soul
    exits:
      - id: done
        label: Done
      - id: retry
        label: Retry
  step_two:
    type: code
    code: |
      def main(data):
          return {"result": data["step_one"].upper()}
    depends: step_one

workflow:
  name: Example Workflow
  entry: step_one

limits:                   # optional — budget constraints
  cost_cap_usd: 1.0
  max_duration_seconds: 300
  on_exceed: fail

eval:                     # optional — test cases
  cases:
    - id: basic_test
      fixtures:
        step_one: "mock output"
```

## Top-level sections

| Section | Type | Default | Description |
|---------|------|---------|-------------|
| `version` | `str` | `"1.0"` | Schema version. Currently only `"1.0"` is supported. |
| `workflow` | `WorkflowDef` | **required** | Graph metadata — the only required section. |
| `blocks` | `Dict[str, BlockDef]` | `{}` | Block definitions keyed by block ID. |
| `souls` | `Dict[str, SoulDef]` | `{}` | Inline soul definitions. Key must match `soul.id`. |
| `tools` | `List[str]` | `[]` | Tool IDs available to souls in this workflow. |
| `limits` | `WorkflowLimitsDef` | none | Workflow-level budget constraints. |
| `eval` | `EvalSectionDef` | none | Embedded test cases for offline evaluation. |
| `enabled` | `bool` | `false` | Whether the workflow is active. |
| `config` | `Dict[str, Any]` | `{}` | Arbitrary workflow configuration. |
| `interface` | `WorkflowInterfaceDef` | none | Public input/output contract for callable sub-workflows. |

## workflow

The graph definition. This is the only required top-level section.

```yaml
workflow:
  name: My Workflow
  entry: step_one
  transitions:
    - from: step_one
      to: step_two
    - from: step_two
      to: null  # terminal
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | required | Workflow name |
| `entry` | `str` | required | Block ID to start execution |
| `transitions` | `List[TransitionDef]` | `[]` | Simple A→B transitions |
| `conditional_transitions` | `List[ConditionalTransitionDef]` | `[]` | Multi-path transitions based on output |

### TransitionDef

```yaml
transitions:
  - from: step_a
    to: step_b
  - from: step_b
    to: null    # terminal — workflow ends after this block
```

| Field | Type | Description |
|-------|------|-------------|
| `from` | `str` | Source block ID |
| `to` | `str` or `null` | Target block ID, or `null` for terminal |

### ConditionalTransitionDef

```yaml
conditional_transitions:
  - from: classifier
    urgent: handle_urgent
    normal: handle_normal
    default: handle_normal
```

| Field | Type | Description |
|-------|------|-------------|
| `from` | `str` | Source block ID |
| `default` | `str` or `null` | Fallback target if no key matches |
| *(extra keys)* | `str` | Decision key → target block ID |

:::tip[DX shorthand: `depends`]
Instead of writing explicit transitions, you can use `depends` on individual blocks:
```yaml
blocks:
  step_a:
    type: linear
    soul_ref: analyst
  step_b:
    type: linear
    soul_ref: writer
    depends: step_a      # equivalent to transition from: step_a, to: step_b
```
See [YAML DX Shortcuts](/docs/workflows/yaml-dx-shortcuts) for more.
:::

## blocks

Block definitions are keyed by block ID and use a discriminated union on the `type` field. See [Block Types](/docs/workflows/block-types) for the complete reference.

All blocks share these common fields from `BaseBlockDef`:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | `str` | required | Block type discriminator |
| `depends` | `str` or `List[str]` | none | Upstream block dependencies |
| `error_route` | `str` | none | Target block on error |
| `exits` | `List[ExitDef]` | none | Named exit ports for branching |
| `exit_conditions` | `List[ExitCondition]` | none | Output pattern → exit handle mapping |
| `assertions` | `List[Dict]` | none | Block-level quality assertions |
| `retry_config` | `RetryConfig` | none | Retry on failure |
| `timeout_seconds` | `int` | `300` | Block execution timeout (1–3600 seconds) |
| `limits` | `BlockLimitsDef` | none | Per-block budget constraints |
| `stateful` | `bool` | `false` | Maintain conversation history across re-invocations |
| `inputs` | `Dict[str, InputRef]` | none | Explicit upstream data references |
| `outputs` | `Dict[str, str]` | none | Output field name → type string |
| `output_conditions` | `List[CaseDef]` | none | Named output branches (mutually exclusive with `routes`) |
| `routes` | `List[RouteDef]` | none | Shorthand routing (mutually exclusive with `output_conditions`) |

### ExitDef

```yaml
exits:
  - id: approve
    label: Approved by reviewer
  - id: reject
    label: Rejected — needs revision
```

### ExitCondition

Maps output patterns to exit handles:

```yaml
exit_conditions:
  - contains: "APPROVED"
    exit_handle: approve
  - regex: "reject|deny"
    exit_handle: reject
```

### RetryConfig

```yaml
retry_config:
  max_attempts: 3
  backoff: exponential
  backoff_base_seconds: 2.0
```

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `max_attempts` | `int` | `3` | 1–20 | Maximum retry attempts |
| `backoff` | `str` | `"fixed"` | `"fixed"` or `"exponential"` | Backoff strategy |
| `backoff_base_seconds` | `float` | `1.0` | 0.1–60.0 | Base delay between retries |
| `non_retryable_errors` | `List[str]` | none | — | Error types that should not be retried |

### InputRef

Explicit reference to upstream block output:

```yaml
inputs:
  summary:
    from: research_step.output
```

## limits

Budget constraints at the workflow or block level.

### WorkflowLimitsDef

```yaml
limits:
  cost_cap_usd: 5.0
  max_duration_seconds: 600
  token_cap: 50000
  on_exceed: fail        # "warn" or "fail"
  warn_at_pct: 0.8       # 0.0–1.0, triggers warning at this threshold
```

| Field | Type | Default | Constraints |
|-------|------|---------|-------------|
| `cost_cap_usd` | `float` | none | >= 0.0 |
| `max_duration_seconds` | `int` | none | 1–86400 |
| `token_cap` | `int` | none | >= 1 |
| `on_exceed` | `str` | `"fail"` | `"warn"` or `"fail"` |
| `warn_at_pct` | `float` | `0.8` | 0.0–1.0 |

### BlockLimitsDef

Same fields as `WorkflowLimitsDef` minus `warn_at_pct`. Applied per block via the `limits` field:

```yaml
blocks:
  expensive_step:
    type: linear
    soul_ref: analyst
    limits:
      cost_cap_usd: 0.50
      max_duration_seconds: 60
      on_exceed: fail
```

## eval

Embedded test cases for offline evaluation. Run without LLM calls using fixture mode.

```yaml
eval:
  threshold: 0.8         # 0.0–1.0, optional pass rate threshold
  cases:
    - id: test_summary
      description: Verify summary output
      inputs:
        topic: "machine learning"
      fixtures:
        research: "ML is a subset of AI..."
      expected:
        summarize:
          - type: contains
            value: "machine learning"
          - type: word-count
            min: 50
            max: 200
```

### EvalCaseDef

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | `str` | required | Unique test case ID |
| `description` | `str` | none | Human-readable description |
| `inputs` | `Dict[str, Any]` | none | Input data for the workflow |
| `fixtures` | `Dict[str, str]` | none | Block ID → mock output (skips LLM calls) |
| `expected` | `Dict[str, List[Dict]]` | none | Block ID → list of assertions |

## interface

Public contract for sub-workflows called via `workflow` blocks.

```yaml
interface:
  inputs:
    - name: topic
      target: research.instruction
      type: string
      required: true
    - name: max_words
      target: config.max_words
      type: integer
      required: false
      default: 500
  outputs:
    - name: summary
      source: summarize.output
      type: string
```

### WorkflowInterfaceInputDef

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | required | Input parameter name (must be unique) |
| `target` | `str` | required | Dot-notation path to child state key |
| `type` | `str` | none | Type hint |
| `required` | `bool` | `true` | Whether input must be provided |
| `default` | `Any` | none | Default value if not provided |
| `description` | `str` | none | Human-readable description |

### WorkflowInterfaceOutputDef

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | required | Output parameter name (must be unique) |
| `source` | `str` | required | Dot-notation path to child result |
| `type` | `str` | none | Type hint |
| `description` | `str` | none | Human-readable description |

## JSON schema for editors

A JSON schema is auto-generated from the Pydantic models for Monaco editor autocomplete:

```bash
python packages/core/scripts/generate_schema.py          # generate
python packages/core/scripts/generate_schema.py --check   # verify in sync
```

The generated schema lives at `packages/core/runsight-workflow-schema.json`.
