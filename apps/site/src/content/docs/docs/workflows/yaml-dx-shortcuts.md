---
title: YAML DX Shortcuts
description: "Reference for all YAML authoring shortcuts: depends, error_route, gate pass/fail, routes, and inline souls."
---

<!-- Linear: RUN-666 (YAML DX Sugar Layer) -->

Runsight provides several shorthand features that reduce boilerplate when writing workflow YAML by hand. Each shorthand expands into the full canonical form at parse time — the engine sees the same structures either way.

## depends

**Syntax:** `str` or `List[str]` on any block

Instead of writing explicit transitions in the `workflow` section, declare `depends` on a block to auto-generate a transition from the dependency to the dependent block.

```yaml title="with depends"
blocks:
  research:
    type: linear
    soul_ref: researcher
  draft:
    type: linear
    soul_ref: writer
    depends: research

workflow:
  name: Pipeline
  entry: research
```

This is equivalent to:

```yaml title="without depends (expanded form)"
blocks:
  research:
    type: linear
    soul_ref: researcher
  draft:
    type: linear
    soul_ref: writer

workflow:
  name: Pipeline
  entry: research
  transitions:
    - from: research
      to: draft
```

### Multiple dependencies

Use a list to depend on multiple blocks:

```yaml
blocks:
  final:
    type: code
    code: |
      def main(data):
          return {"combined": True}
    depends:
      - step_a
      - step_b
```

Each entry generates a separate transition: `step_a -> final` and `step_b -> final`.

### Conflict detection

If a dependency already has a transition defined (either explicit or from another `depends`), the parser raises a `ValueError`. Each block can only have one outgoing plain transition.

```yaml title="this will fail"
blocks:
  step_a:
    type: linear
    soul_ref: s1
  step_b:
    type: linear
    soul_ref: s2
    depends: step_a
  step_c:
    type: linear
    soul_ref: s3
    depends: step_a    # error: step_a already transitions to step_b
```

## error_route

**Syntax:** `str` on any block

Specifies a target block that runs when the current block fails with an exception. The engine catches the error, stores error information in `shared_memory` under `__error__{block_id}`, and routes to the target block.

```yaml
blocks:
  risky_step:
    type: linear
    soul_ref: experimental
    error_route: handle_error
  handle_error:
    type: code
    code: |
      def main(data):
          error_info = data.get("__error__risky_step", {})
          return {"recovered": True, "error": error_info.get("message", "")}

workflow:
  name: Error Recovery
  entry: risky_step
  transitions:
    - from: risky_step
      to: next_step
    - from: handle_error
      to: next_step
```

Error routes also catch **soft errors**: if a block completes normally but its `exit_handle` is `"error"` (for example, a workflow block with `on_error: catch`), the engine routes to the error target instead of the normal transition.

The error information stored in `shared_memory` includes:

| Key | Description |
|-----|-------------|
| `type` | Exception class name (e.g. `"ValueError"`) |
| `message` | Exception message string |

## Gate pass/fail shorthand

**Syntax:** `pass` and `fail` fields on `gate` blocks

Gate blocks produce a `"pass"` or `"fail"` exit handle based on the LLM's judgment. The `pass` and `fail` fields are shorthand for declaring exit ports and conditional transitions.

```yaml title="with shorthand"
blocks:
  quality_check:
    type: gate
    soul_ref: reviewer
    eval_key: draft
    pass: publish
    fail: revise
```

This expands to:

```yaml title="expanded form"
blocks:
  quality_check:
    type: gate
    soul_ref: reviewer
    eval_key: draft
    exits:
      - id: pass
        label: Pass
      - id: fail
        label: Fail

workflow:
  conditional_transitions:
    - from: quality_check
      pass: publish
      fail: revise
      default: revise
```

Both `pass` and `fail` must be set together, or both omitted. Setting only one raises a validation error. When the shorthand is used, the `default` conditional transition target is set to the `fail` target.

## Routes shorthand

**Syntax:** `routes` list on any block

Routes combine output conditions and conditional transitions in a single declaration. They are mutually exclusive with `output_conditions` — using both on the same block raises a validation error.

```yaml title="routes shorthand"
blocks:
  review:
    type: code
    code: |
      def main(data):
          return {"status": "approved"}
    routes:
      - case: publish
        when:
          conditions:
            - eval_key: status
              operator: equals
              value: approved
        goto: publish
      - case: archive
        default: true
        goto: archive
```

Each route has:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `case` | `str` | required | Case identifier |
| `when` | `ConditionGroupDef` | none | Conditions to evaluate (ignored on default routes) |
| `goto` | `str` | required | Target block ID |
| `default` | `bool` | `false` | Whether this is the fallback route |

Routes require **exactly one** default route. Duplicate `case` values raise a validation error.

At parse time, routes expand into:
1. `output_conditions` with `CaseDef` entries for each route
2. A `conditional_transition` mapping each case ID to its `goto` target

### Condition operators

The `when` block uses the same condition engine as `output_conditions`. See [Transitions & Routing](/docs/workflows/transitions-and-routing#supported-operators) for the full operator list.

## Inline souls

**Syntax:** `souls` section at the workflow top level

Souls are primarily defined as external library files under `custom/souls/`. The inline `souls:` section lets you define souls directly in the workflow YAML for convenience. Inline souls override external ones with the same ID (with a warning logged).

```yaml title="inline soul definition"
souls:
  quick_reviewer:
    id: quick_reviewer
    kind: soul
    name: Quick Reviewer
    role: Reviewer
    system_prompt: "Review the content for clarity and accuracy."
    model_name: gpt-4.1-mini
    temperature: 0.3

blocks:
  review:
    type: gate
    soul_ref: quick_reviewer
    eval_key: draft
    pass: done
    fail: revise
```

The key in the `souls` dict **must match** the soul's `id` field. A mismatch raises a validation error.

### Soul fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | `str` | required | Must match the dict key |
| `kind` | `"soul"` | required | Entity kind |
| `name` | `str` | required | Human-readable display name |
| `role` | `str` | required | Soul's role name |
| `system_prompt` | `str` | required | System prompt for the LLM |
| `model_name` | `str` | none | Model to use (e.g. `gpt-4.1-mini`) |
| `provider` | `str` | none | Provider name |
| `temperature` | `float` | none | Sampling temperature |
| `max_tokens` | `int` | none | Max output tokens |
| `tools` | `List[str]` | none | Tool IDs this soul can use |
| `required_tool_calls` | `List[str]` | none | Tools the soul must call |
| `max_tool_iterations` | `int` | `5` | Max tool call rounds |
| `avatar_color` | `str` | none | Color for UI rendering |

:::tip
Use inline souls for quick prototyping or one-off workflows. For souls shared across multiple workflows, define them as external files in `custom/souls/` so they stay in sync.
:::

## Combining shortcuts

All shortcuts can be used together. Here is a compact workflow using `depends`, `error_route`, gate `pass`/`fail`, inline `souls`, and `routes`:

```yaml title="all shortcuts combined"
version: "1.0"
id: compact-pipeline
kind: workflow

souls:
  writer:
    id: writer
    kind: soul
    name: Writer
    role: Writer
    system_prompt: "Write a concise summary."
    model_name: gpt-4.1-mini
  reviewer:
    id: reviewer
    kind: soul
    name: Reviewer
    role: Reviewer
    system_prompt: "Evaluate the summary for accuracy."
    model_name: gpt-4.1-mini

blocks:
  research:
    type: linear
    soul_ref: writer
    error_route: fallback
  draft:
    type: linear
    soul_ref: writer
    depends: research
  quality_gate:
    type: gate
    soul_ref: reviewer
    eval_key: draft
    pass: publish
    fail: draft
    depends: draft
  publish:
    type: code
    code: |
      def main(data):
          return {"published": True}
  fallback:
    type: code
    code: |
      def main(data):
          return {"error": "research failed"}

workflow:
  name: Compact Pipeline
  entry: research
```
