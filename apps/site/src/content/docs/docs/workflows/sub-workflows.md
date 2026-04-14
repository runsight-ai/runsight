---
title: Sub-Workflows
description: Compose workflows by nesting one inside another — parent-child run linkage, input/output mapping, error handling, and callable contracts.
---

<!-- Linear: RUN-598 (Sub-Workflow Execution), RUN-610 (Post-MVP artifact governance — cut) -->

The `workflow` block type lets you execute an entire child workflow as a single step in a parent workflow. The child runs in an isolated state, with explicit input/output mapping as the only channel between parent and child. This implements a Hierarchical State Machine (HSM) pattern.

## When to use sub-workflows

Use sub-workflows when you have a reusable pipeline that multiple parent workflows call, or when you want to encapsulate a complex sequence behind a clean interface. Common patterns:

- A "summarize" sub-workflow called by different analysis pipelines
- A "review and revise" loop packaged as a reusable unit
- Breaking a large workflow into composable, testable pieces

## Define the child workflow

The child workflow is a standard YAML workflow file with an `interface` section that declares its public inputs and outputs. The interface is required — the engine rejects workflow blocks that reference children without one.

```yaml title="custom/workflows/summarizer.yaml"
version: "1.0"
id: summarizer
kind: workflow

interface:
  inputs:
    - name: topic
      target: shared_memory.topic
      type: string
      required: true
    - name: max_words
      target: shared_memory.max_words
      type: integer
      required: false
      default: 500
  outputs:
    - name: summary
      source: results.summarize
      type: string

blocks:
  research:
    type: linear
    soul_ref: researcher
  summarize:
    type: linear
    soul_ref: writer
    depends: research

workflow:
  name: Summarizer
  entry: research
```

### Interface input fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | required | Input parameter name (must be unique) |
| `target` | `str` | required | Dot-notation path into the child's state (e.g. `shared_memory.topic`) |
| `type` | `str` | none | Type hint for documentation |
| `required` | `bool` | `true` | Whether the parent must provide this input |
| `default` | `Any` | none | Default value when the parent omits this input |
| `description` | `str` | none | Human-readable description |

### Interface output fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | required | Output parameter name (must be unique) |
| `source` | `str` | required | Dot-notation path in child's final state (e.g. `results.summarize`) |
| `type` | `str` | none | Type hint for documentation |
| `description` | `str` | none | Human-readable description |

## Call the child from a parent

In the parent workflow, add a `workflow` block with `workflow_ref` pointing to the child, and map inputs and outputs using interface names.

```yaml title="custom/workflows/analysis-pipeline.yaml"
version: "1.0"
id: analysis-pipeline
kind: workflow

blocks:
  gather:
    type: linear
    soul_ref: collector
  run_summary:
    type: workflow
    workflow_ref: summarizer
    inputs:
      topic: results.gather          # interface name → parent state path
    outputs:
      results.final_summary: summary  # parent state path → interface name
    on_error: catch
    depends: gather
  present:
    type: linear
    soul_ref: presenter
    depends: run_summary

workflow:
  name: Analysis Pipeline
  entry: gather
```

### Workflow block fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `workflow_ref` | `str` | required | Embedded workflow id of the child workflow |
| `inputs` | `Dict[str, str]` | none | Interface name mapped to parent state path |
| `outputs` | `Dict[str, str]` | none | Parent state path mapped to interface output name |
| `max_depth` | `int` | none | Maximum nesting depth (falls back to `config.max_workflow_depth`, default `10`) |
| `on_error` | `str` | `"raise"` | `"raise"` or `"catch"` |

### Input mapping

Input keys are **interface names** (plain strings like `topic`), not child state paths. The engine resolves the interface name to the child's `target` path. The values are parent state paths using dot-notation: `results.gather`, `shared_memory.topic`, `current_task`.

### Output mapping

Output keys are **parent state paths** where values get written. Output values are **interface names** from the child's interface. The engine resolves the interface name to the child's `source` path and copies the value into the parent state.

## Error handling

The `on_error` field controls what happens when the child workflow fails.

### on_error: raise (default)

The child's exception propagates to the parent. The parent workflow fails at the workflow block. If the parent block has an `error_route`, the engine routes there.

### on_error: catch

The parent workflow continues even if the child fails. The workflow block produces a `BlockResult` with:
- `exit_handle: "error"`
- `output`: an error description string
- `metadata`: includes `child_status: "failed"`, `child_error`, `child_cost_usd`, `child_tokens`, `child_duration_s`

This also catches **soft errors** — if any child block completed with `exit_handle: "error"`, the parent treats the entire child run as failed.

```yaml title="catch pattern with error routing"
blocks:
  risky_sub:
    type: workflow
    workflow_ref: experimental-pipeline
    on_error: catch
    error_route: fallback
  fallback:
    type: linear
    soul_ref: fallback_handler
```

## Parent-child run linkage

Each sub-workflow execution creates a separate run record linked to the parent run. The child gets its own observer for independent monitoring. The `BlockResult.metadata` on the parent includes `child_run_id` for drill-down.

Cost and token usage from the child are propagated back to the parent — `total_cost_usd` and `total_tokens` accumulate across the hierarchy.

## State isolation

The child workflow receives a **clean** `WorkflowState`. It does not inherit the parent's results, shared memory, or execution log. The only data the child sees is what the parent explicitly passes through `inputs`.

Similarly, the parent only receives data from the child through the `outputs` mapping. No results leak from child to parent outside of the declared interface.

## Depth limits and cycle detection

The engine tracks a **call stack** of workflow names during execution. Two safety mechanisms prevent runaway recursion:

- **Cycle detection**: if a workflow name already appears in the call stack, the engine raises a `RecursionError`. A workflow cannot call itself, directly or indirectly.
- **Depth limit**: the call stack depth is checked against `max_depth` before each child execution. The default limit is `10`, configurable per-block or via `config.max_workflow_depth` in the workflow file.

## Workflow ref resolution

The `workflow_ref` value resolves only to the embedded workflow id of the child workflow. Path, filename, relative-path, and display-name aliases are not accepted.

Use `workflow_ref: summarizer` when the child file is `custom/workflows/summarizer.yaml` and the YAML contains `id: summarizer`.
