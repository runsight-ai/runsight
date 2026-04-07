---
title: Block Types
description: The six block types in Runsight — linear, gate, code, loop, workflow, and dispatch.
---

Every block in a workflow has a `type` field that determines its behavior. All blocks share the [common fields](/docs/workflows/yaml-schema#blocks) from `BaseBlockDef` — this page covers the type-specific fields.

## linear

Single LLM call through a soul. The most common block type.

```yaml
blocks:
  research:
    type: linear
    soul_ref: researcher
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `soul_ref` | `str` | required | Soul ID to use for this block |

The soul receives the current workflow state as context and its `system_prompt` as the system message. The LLM response becomes the block's output, stored at `state.results[block_id]`.

If the block has `exits` defined, the soul can use the `delegate` tool to pick an exit port — see [Dispatch & Delegate](/docs/tools/dispatch-and-delegate).

## gate

LLM quality gate — evaluates another block's output and routes on pass/fail.

```yaml
blocks:
  quality_check:
    type: gate
    soul_ref: reviewer
    eval_key: draft_step
    pass: publish
    fail: revise
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `soul_ref` | `str` | required | Soul ID for the gate evaluator |
| `eval_key` | `str` | required | Block ID whose output is being evaluated |
| `extract_field` | `str` | none | JSON field to extract from the target block's output before evaluation |
| `pass` | `str` | none | Target block on pass (shorthand for exit routing) |
| `fail` | `str` | none | Target block on fail (shorthand for exit routing) |

The gate soul receives the output of `eval_key` and makes a pass/fail judgment. If `extract_field` is set, only that JSON field is extracted before the soul sees it.

`pass` and `fail` are shorthand for exit ports — they automatically create two `ExitDef` entries with IDs `"pass"` and `"fail"`. Both must be set together or both omitted. When omitted, the gate result is determined by the soul's output and standard exit conditions.

## code

Runs Python code in a sandboxed environment. The code must define a `def main(data)` function.

```yaml
blocks:
  transform:
    type: code
    code: |
      import json

      def main(data):
          raw = data.get("research", "")
          parsed = json.loads(raw) if raw.startswith("{") else {"text": raw}
          return {"structured": parsed}
    timeout_seconds: 15
    allowed_imports: [json, re]
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `code` | `str` | required | Python source code with a `def main(data)` function |
| `timeout_seconds` | `int` | `30` | Execution timeout in seconds (overrides base default of 300) |
| `allowed_imports` | `List[str]` | safe whitelist | Whitelist of importable modules. If omitted, defaults to: `json`, `re`, `math`, `datetime`, `collections`, `itertools`, `hashlib`, `base64`, `time`, `urllib.parse`. Set explicitly to expand or restrict. |

The `main` function receives a `data` dict containing all upstream block results. It must return a dict — the return value becomes the block's output.

## loop

Iterates inner blocks for multiple rounds with optional break conditions.

```yaml
blocks:
  refine:
    type: loop
    inner_block_refs: [draft, review]
    max_rounds: 3
    break_condition:
      eval_key: review.verdict
      operator: equals
      value: approved
    carry_context:
      enabled: true
      mode: last
      inject_as: previous_feedback
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `inner_block_refs` | `List[str]` | required | Block IDs to execute each round (min 1) |
| `max_rounds` | `int` | `5` | Maximum iterations (1–50) |
| `break_condition` | `ConditionDef` or `ConditionGroupDef` | none | Condition to exit the loop early |
| `carry_context` | `CarryContextConfig` | none | Pass context between rounds |
| `break_on_exit` | `str` | none | Exit handle that triggers loop break |
| `retry_on_exit` | `str` | none | Exit handle that triggers another round |

### CarryContextConfig

Controls how context flows between loop rounds:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `true` | Enable context carrying |
| `mode` | `str` | `"last"` | `"last"` (only previous round) or `"all"` (accumulate all rounds) |
| `source_blocks` | `List[str]` | none | Specific blocks to carry from (default: all inner blocks) |
| `inject_as` | `str` | `"previous_round_context"` | Key name for injected context |

If `stateful: true` is set on inner blocks, they maintain conversation history across rounds — the soul remembers prior iterations.

## workflow

Executes a child workflow as a sub-step. Parent-child run linkage, independent error handling.

```yaml
blocks:
  sub_pipeline:
    type: workflow
    workflow_ref: analysis-pipeline
    inputs:
      topic: research.output
    outputs:
      summary: analysis.result
    on_error: catch
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `workflow_ref` | `str` | required | ID of the child workflow file to execute |
| `inputs` | `Dict[str, str]` | none | Parent state key → child state key mapping |
| `outputs` | `Dict[str, str]` | none | Parent path → child dotted path mapping |
| `max_depth` | `int` | none | Maximum nesting depth limit |
| `on_error` | `str` | `"raise"` | `"raise"` (propagate) or `"catch"` (absorb error, continue parent) |

The child workflow runs as a separate execution with its own run record linked to the parent. The child's blocks execute independently — they do not see the parent's state unless explicitly mapped via `inputs`.

When `on_error: catch` is set, the parent workflow continues execution even if the child fails.

## dispatch

Parallel branching — each exit port gets its own soul and task instruction. All branches execute concurrently.

```yaml
blocks:
  analyze:
    type: dispatch
    exits:
      - id: sentiment
        label: Sentiment Analysis
        soul_ref: sentiment_analyst
        task: Analyze the sentiment of the input text.
      - id: entities
        label: Entity Extraction
        soul_ref: entity_extractor
        task: Extract all named entities from the input.
```

The dispatch block uses `DispatchExitDef` (not the standard `ExitDef`):

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique exit port ID |
| `label` | `str` | Human-readable label |
| `soul_ref` | `str` | Soul ID for this branch |
| `task` | `str` | Task instruction for this branch's soul |

All branches run concurrently via `asyncio.gather`. Each branch gets its own budget session for cost isolation. Results are stored per-exit at `state.results["{block_id}.{exit_id}"]` and combined at `state.results[block_id]` as a JSON array.

:::note[dispatch vs delegate]
`dispatch` is a block type — it runs all exit branches in parallel with no tool involvement. `delegate` is a builtin tool that a soul can call on any block with exits (typically `linear`) to pick one exit port for LLM-driven routing. Dispatch does not use delegate.
:::

## Common patterns

### Sequential pipeline

```yaml
blocks:
  step_a:
    type: linear
    soul_ref: researcher
  step_b:
    type: linear
    soul_ref: writer
    depends: step_a
  step_c:
    type: gate
    soul_ref: reviewer
    eval_key: step_b
    depends: step_b
workflow:
  name: Pipeline
  entry: step_a
```

### Loop with quality gate

```yaml
blocks:
  draft:
    type: linear
    soul_ref: writer
    stateful: true
  review:
    type: gate
    soul_ref: reviewer
    eval_key: draft
    pass: done
    fail: draft
  refine_loop:
    type: loop
    inner_block_refs: [draft, review]
    max_rounds: 3
    break_on_exit: pass
    carry_context:
      enabled: true
      mode: last
  done:
    type: code
    code: |
      def main(data):
          return {"final": data.get("draft", "")}
    depends: refine_loop
workflow:
  name: Iterative Refinement
  entry: refine_loop
```
