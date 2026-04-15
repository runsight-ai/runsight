---
title: Block Type Reference
description: Quick-reference card for every block type — all fields, defaults, and minimal YAML examples.
---

<!-- RUN-110 -->

Compact lookup reference for all six block types. For detailed explanations and common patterns, see [Block Types](/docs/workflows/block-types).

## Common fields (BaseBlockDef)

Every block inherits these fields regardless of type.

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `type` | `str` | -- | required | Block type discriminator (`linear`, `gate`, `code`, `loop`, `workflow`, `dispatch`, `synthesize`) |
| `stateful` | `bool` | `false` | -- | Maintain conversation history across re-invocations |
| `depends` | `str` or `List[str]` | none | non-blank | Upstream block dependencies |
| `error_route` | `str` | none | non-blank | Target block on error |
| `inputs` | `Dict[str, InputRef]` | none | -- | Explicit upstream data references (each entry has a `from` field) |
| `outputs` | `Dict[str, str]` | none | -- | Output field name to type string mapping |
| `output_conditions` | `List[CaseDef]` | none | mutually exclusive with `routes` | Named output branches |
| `routes` | `List[RouteDef]` | none | mutually exclusive with `output_conditions`, requires exactly one default | Shorthand routing |
| `exits` | `List[ExitDef]` | none | -- | Named exit ports for branching |
| `exit_conditions` | `List[ExitCondition]` | none | -- | Output pattern to exit handle mapping |
| `assertions` | `List[Dict[str, Any]]` | none | -- | Block-level quality assertions |
| `retry_config` | `RetryConfig` | none | -- | Retry on failure |
| `timeout_seconds` | `int` | `300` | 1--3600 | Block execution timeout in seconds |
| `stall_thresholds` | `Dict[str, int]` | none | -- | Per-phase stall detection thresholds |
| `limits` | `BlockLimitsDef` | none | -- | Per-block budget constraints |

---

## linear

Single LLM call through a soul.

| Field | Type | Default | Required | Description |
|-------|------|---------|----------|-------------|
| `type` | `Literal["linear"]` | `"linear"` | **yes** | Type discriminator |
| `soul_ref` | `str` | -- | **yes** | Soul ID to use for this block |

```yaml title="minimal linear block"
blocks:
  research:
    type: linear
    soul_ref: researcher
```

---

## gate

LLM quality gate -- evaluates another block's output and routes on pass/fail.

| Field | Type | Default | Required | Description |
|-------|------|---------|----------|-------------|
| `type` | `Literal["gate"]` | `"gate"` | **yes** | Type discriminator |
| `soul_ref` | `str` | -- | **yes** | Soul ID for the gate evaluator |
| `eval_key` | `str` | -- | **yes** | Block ID whose output is being evaluated |
| `extract_field` | `str` | none | no | JSON field to extract before evaluation |
| `pass` | `str` | none | no | Target block on pass (shorthand). Must be set with `fail`. |
| `fail` | `str` | none | no | Target block on fail (shorthand). Must be set with `pass`. |

When `pass` and `fail` are omitted, the gate auto-creates two `ExitDef` entries with IDs `"pass"` and `"fail"`.

```yaml title="minimal gate block"
blocks:
  quality_check:
    type: gate
    soul_ref: reviewer
    eval_key: draft
    pass: publish
    fail: revise
```

---

## code

Sandboxed Python code execution. No LLM calls.

| Field | Type | Default | Required | Description |
|-------|------|---------|----------|-------------|
| `type` | `Literal["code"]` | `"code"` | **yes** | Type discriminator |
| `code` | `str` | -- | **yes** | Python source code containing `def main(data)` |
| `timeout_seconds` | `int` | `30` | no | Execution timeout (overrides base default of 300) |
| `allowed_imports` | `List[str]` | `["json", "re", "math", "datetime", "collections", "itertools", "hashlib", "base64", "time", "urllib.parse"]` | no | Whitelist of importable modules |

The `main` function receives a `data` dict with keys `results`, `metadata`, and `shared_memory`. It must return a JSON-serializable value. If the return value is a dict containing `exit_handle`, that value is extracted and used as the block's exit handle.

```yaml title="minimal code block"
blocks:
  transform:
    type: code
    code: |
      def main(data):
          return {"count": len(data.get("results", {}))}
```

---

## loop

Iterates inner blocks for multiple rounds with optional break conditions.

| Field | Type | Default | Required | Constraints | Description |
|-------|------|---------|----------|-------------|-------------|
| `type` | `Literal["loop"]` | `"loop"` | **yes** | -- | Type discriminator |
| `inner_block_refs` | `List[str]` | -- | **yes** | min 1 item | Block IDs to execute each round |
| `max_rounds` | `int` | `5` | no | 1--50 | Maximum iterations |
| `break_condition` | `ConditionDef` or `ConditionGroupDef` | none | no | -- | Condition evaluated against last inner block's output |
| `carry_context` | `CarryContextConfig` | none | no | -- | Context propagation between rounds |
| `break_on_exit` | `str` | none | no | -- | Exit handle value that triggers loop break |
| `retry_on_exit` | `str` | none | no | -- | Exit handle value that triggers another round |

### CarryContextConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `true` | Enable context carrying |
| `mode` | `str` | `"last"` | `"last"` (previous round only) or `"all"` (accumulate all rounds) |
| `source_blocks` | `List[str]` | none | Specific blocks to carry from (default: all inner blocks). Must be subset of `inner_block_refs`. |
| `inject_as` | `str` | `"previous_round_context"` | Key name for injected context in `shared_memory` |

```yaml title="minimal loop block"
blocks:
  refine:
    type: loop
    inner_block_refs: [draft, review]
    max_rounds: 3
    break_on_exit: pass
```

---

## workflow

Executes a child workflow as a sub-step (Hierarchical State Machine pattern).

| Field | Type | Default | Required | Description |
|-------|------|---------|----------|-------------|
| `type` | `Literal["workflow"]` | `"workflow"` | **yes** | Type discriminator |
| `workflow_ref` | `str` | -- | **yes** | Embedded workflow id of the child workflow to execute |
| `inputs` | `Dict[str, str]` | none | no | Interface name to parent state path mapping. Keys must not contain dots. |
| `outputs` | `Dict[str, str]` | none | no | Parent path to interface name mapping. Values must not contain dots. |
| `max_depth` | `int` | none | no | Maximum nesting depth limit (default engine limit is 10) |
| `on_error` | `str` | `"raise"` | no | `"raise"` (propagate error) or `"catch"` (absorb error, continue parent) |

```yaml title="minimal workflow block"
blocks:
  sub_pipeline:
    type: workflow
    workflow_ref: analysis-pipeline
    inputs:
      topic: results.research
    outputs:
      results.summary: analysis_result
```

---

## synthesize

Combines outputs from multiple upstream blocks into a single result via an LLM.

| Field | Type | Default | Required | Description |
|-------|------|---------|----------|-------------|
| `type` | `Literal["synthesize"]` | `"synthesize"` | **yes** | Type discriminator |
| `soul_ref` | `str` | -- | **yes** | Soul ID for the synthesizer |
| `input_block_ids` | `List[str]` | -- | **yes** | Block IDs whose outputs are combined (must be non-empty) |

```yaml title="minimal synthesize block"
blocks:
  combine:
    type: synthesize
    soul_ref: synthesizer
    input_block_ids: [research, code_review, design]
```

---

## dispatch

Parallel branching -- each exit port gets its own soul and task instruction. All branches execute concurrently.

| Field | Type | Default | Required | Description |
|-------|------|---------|----------|-------------|
| `type` | `Literal["dispatch"]` | `"dispatch"` | **yes** | Type discriminator |
| `exits` | `List[DispatchExitDef]` | -- | **yes** | Exit port definitions with per-branch soul and task |

### DispatchExitDef

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | **yes** | Unique exit port ID |
| `label` | `str` | **yes** | Human-readable label |
| `soul_ref` | `str` | **yes** | Soul ID for this branch |
| `task` | `str` | **yes** | Task instruction for this branch's soul |

Results are stored per-exit at `state.results["{block_id}.{exit_id}"]` and combined at `state.results[block_id]` as a JSON array.

```yaml title="minimal dispatch block"
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
