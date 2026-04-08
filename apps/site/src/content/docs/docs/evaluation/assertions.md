---
title: Assertions
description: All block-level assertion types, their parameters, and how pass/fail is computed per node.
---

Assertions are quality checks that run automatically after a block completes. You define them directly on a block in your workflow YAML, and the engine evaluates each one against the block's output. Every assertion produces a pass/fail result and a numeric score (0.0 to 1.0).

## Where assertions live

Assertions are defined on the `assertions` field of any block definition. The field accepts a list of assertion config objects:

```yaml title="custom/workflows/research.yaml"
blocks:
  analyze:
    type: llm
    soul_ref: analyst
    assertions:
      - type: contains
        value: "analysis"
      - type: cost
        threshold: 0.05
```

The `assertions` field is declared on `BaseBlockDef` as `Optional[List[Dict[str, Any]]]` and defaults to `None`. Every block type inherits it.

## Assertion config fields

Each assertion in the list is a dict with these fields:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `type` | `str` | yes | -- | Assertion type identifier (see table below) |
| `value` | `any` | depends | `""` | Comparison value. Required for string assertions, optional for performance assertions |
| `threshold` | `float` | no | varies | Numeric threshold. Meaning depends on assertion type |
| `weight` | `float` | no | `1.0` | Weight in the aggregate score calculation |
| `metric` | `str` | no | `None` | Named metric label. When set, the score is stored in `named_scores` under this key |
| `transform` | `str` | no | `None` | Pre-process output before evaluation. See [Transform Hooks](/docs/evaluation/transform-hooks) |

## Assertion types

Runsight ships 15 deterministic assertion types across four categories.

### String assertions

| Type | Value | Behavior |
|------|-------|----------|
| `equals` | `str` | Exact string match. Also attempts JSON deep-equal if both sides parse as JSON |
| `contains` | `str` | Case-sensitive substring check |
| `icontains` | `str` | Case-insensitive substring check |
| `contains-all` | `list[str]` | All items must appear as substrings |
| `contains-any` | `list[str]` | At least one item must appear as a substring |
| `starts-with` | `str` | String prefix check |
| `regex` | `str` | Regex search (uses `re.search`, not full match) |
| `word-count` | `int` or `{min, max}` | Exact count or range check on whitespace-split words |

#### Examples

```yaml title="String assertion examples"
assertions:
  # Exact match
  - type: equals
    value: "approved"

  # Case-insensitive substring
  - type: icontains
    value: "conclusion"

  # All keywords must appear
  - type: contains-all
    value: ["summary", "recommendation", "next steps"]

  # Any keyword is acceptable
  - type: contains-any
    value: ["approve", "accept", "pass"]

  # Regex pattern
  - type: regex
    value: "\\d{4}-\\d{2}-\\d{2}"

  # Word count range
  - type: word-count
    value:
      min: 50
      max: 500
```

### Structural assertions

| Type | Value | Behavior |
|------|-------|----------|
| `is-json` | `dict` (optional JSON Schema) | Validates output is valid JSON. If `value` is provided, validates against a JSON Schema |
| `contains-json` | `dict` (optional JSON Schema) | Finds a JSON substring in the output. Scans for `{` and `[` delimiters. Optional schema validation |

#### Examples

```yaml title="Structural assertion examples"
assertions:
  # Output must be valid JSON
  - type: is-json

  # Output must contain a JSON object matching a schema
  - type: contains-json
    value:
      type: object
      required: ["name", "score"]
      properties:
        name:
          type: string
        score:
          type: number
```

### Performance assertions

| Type | Value | Threshold | Behavior |
|------|-------|-----------|----------|
| `cost` | -- | `float` (USD) | Passes if `cost_usd` from the execution context is at or below `threshold` |
| `latency` | -- | `float` (ms) | Passes if `latency_ms` from the execution context is at or below `threshold` |

Performance assertions read from the `AssertionContext`, not from the block output string. The context is populated with actual execution metrics (cost, latency, tokens) from the `RunNode` record.

```yaml title="Performance assertion examples"
assertions:
  - type: cost
    threshold: 0.10
  - type: latency
    threshold: 5000
```

### Linguistic assertions

| Type | Value | Default threshold | Behavior |
|------|-------|-------------------|----------|
| `levenshtein` | `str` (reference text) | `5` | Edit distance between output and reference. Passes if distance <= threshold |
| `bleu` | `str` (reference text) | `0.5` | BLEU-4 score with smoothing. Passes if score >= threshold |
| `rouge-n` | `str` (reference text) | `0.75` | ROUGE-1 F-measure. Passes if score >= threshold |

```yaml title="Linguistic assertion examples"
assertions:
  - type: levenshtein
    value: "The capital of France is Paris."
    threshold: 10
  - type: bleu
    value: "Machine learning models process data to find patterns."
    threshold: 0.3
```

## Negation with not- prefix

Any assertion type can be negated by prefixing it with `not-`. The engine inverts both the pass/fail boolean and the score (1.0 - original):

```yaml title="Negated assertion"
assertions:
  - type: not-contains
    value: "error"
  - type: not-contains-json
```

## Weighted scoring

When a block has multiple assertions, the aggregate score is a weighted average. Each assertion's `weight` (default `1.0`) determines its contribution:

```yaml title="Weighted assertions"
assertions:
  - type: contains
    value: "recommendation"
    weight: 2.0
  - type: word-count
    value:
      min: 100
    weight: 1.0
  - type: cost
    threshold: 0.05
    weight: 0.5
```

The `AssertionsResult` class accumulates weighted results. Its `aggregate_score` property returns the weighted average: `total_score / total_weight`. The `passed()` method without a threshold returns `True` only if every individual assertion passed.

## Assertion chaining

A block can have any number of assertions. Each assertion runs independently -- they do not share state or depend on each other's results. The engine runs all of them concurrently via `asyncio.gather`, so a failure in one assertion never prevents the others from completing.

This is especially useful with `transform` hooks. Each assertion can target a different field in the block output using its own `json_path` transform:

```yaml title="Multiple assertions with different transforms"
blocks:
  process_order:
    type: llm
    soul_ref: processor
    assertions:
      - type: equals
        value: "completed"
        transform: "json_path:$.status"
      - type: contains
        value: "success"
        transform: "json_path:$.message"
      - type: cost
        threshold: 0.02
```

In this example, the first assertion extracts `$.status` and checks for an exact match, the second extracts `$.message` and checks for a substring, and the third checks execution cost without any transform. All three run in parallel.

If a transform fails on one assertion (e.g., the output is not valid JSON, or the path does not exist), that assertion returns `passed=False` with a descriptive reason. The other assertions still run normally and produce their own results. The aggregate score and pass/fail are then computed across all of them using the standard [weighted scoring](#weighted-scoring) rules.

## How assertions fire during execution

When a workflow runs via the API, the engine wires assertions automatically:

1. The `ExecutionService._build_assertion_configs` method reads `assertions` from each block in the parsed workflow
2. An `EvalObserver` is created with the assertion configs and attached to the workflow run
3. After each block completes, `EvalObserver.on_block_complete` fires:
   - Extracts the block output from `WorkflowState`
   - Builds an `AssertionContext` with output, cost, latency, soul info, and tokens
   - Runs all assertion configs for that block
   - Persists `eval_score`, `eval_passed`, and `eval_results` on the `RunNode` record
   - Emits a `node_eval_complete` SSE event with scores, pass/fail, and baseline delta

The `RunNode` entity stores three eval fields:

| Field | Type | Description |
|-------|------|-------------|
| `eval_score` | `Optional[float]` | Weighted average score across all assertions (0.0 to 1.0) |
| `eval_passed` | `Optional[bool]` | `True` if all individual assertions passed |
| `eval_results` | `Optional[Dict]` | Detailed results with per-assertion type, passed, score, and reason |

These fields are `None` when a block has no assertions configured.

<!-- Linear: RUN-555, RUN-693, RUN-685, RUN-705 -- last verified against codebase 2026-04-07 -->
