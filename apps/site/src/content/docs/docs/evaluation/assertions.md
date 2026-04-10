---
title: Assertions
description: Built-in and custom block-level assertions, their config fields, and how Runsight computes eval results.
---

Assertions are quality checks that run after a block completes. You define them directly in workflow YAML, and each assertion produces a pass/fail result plus a numeric score from `0.0` to `1.0`.

Runsight ships 15 built-in deterministic assertion types. You can also add your own scanner-discovered Python assertions under `custom/assertions/`. See [Custom Assertions](/docs/evaluation/custom-assertions) for the custom plugin workflow.

## Where assertions live

Assertions are defined on the `assertions` field of any block definition. The field accepts a list of assertion config objects:

```yaml title="custom/workflows/research.yaml"
version: "1.0"
blocks:
  analyze:
    type: code
    code: |
      def main(data):
          return "analysis ready"
    assertions:
      - type: contains
        value: "analysis"
      - type: cost
        threshold: 0.05
workflow:
  name: assertions_demo
  entry: analyze
  transitions:
    - from: analyze
      to: null
```

The `assertions` field is declared on `BaseBlockDef` as `Optional[List[Dict[str, Any]]]` and defaults to `None`.

## Assertion config fields

Each assertion in the list is a dict with these fields:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `type` | `str` | yes | -- | Assertion type identifier. For custom assertions, use `custom:<file_stem>` |
| `value` | `any` | depends | `""` | Comparison value. Required for most string and linguistic assertions |
| `threshold` | `float` | no | varies | Numeric threshold. Meaning depends on assertion type |
| `config` | `any` | no | `None` | Per-assertion config payload. Built-ins ignore it. Custom assertions receive it as `context["config"]` |
| `weight` | `float` | no | `1.0` | Weight in the aggregate score calculation |
| `metric` | `str` | no | `None` | Named metric label. When set, the score is stored in `named_scores` under this key |
| `transform` | `str` | no | `None` | Pre-process output before evaluation. See [Transform Hooks](/docs/evaluation/transform-hooks) |

## Built-in assertion types

Runsight ships 15 deterministic assertion types across four categories.

### String assertions

| Type | Value | Behavior |
|------|-------|----------|
| `equals` | `str` | Exact string match. Use `config: {mode: json}` to opt into JSON deep-equal |
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

Performance assertions read from the `AssertionContext`, not from the block output string. In live API runs that context is populated with run metrics such as cost, latency, and tokens; offline eval uses zeroed metric fields.

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

## Custom assertions

Beyond the 15 built-in types, you can create your own assertions in Python. The contract is **promptfoo-compatible** — existing promptfoo assertion functions work with minimal changes. Custom assertions are discovered from manifest files under `custom/assertions/*.yaml` and are referenced by file stem:

```yaml title="Custom assertion usage"
assertions:
  - type: custom:tone_check
    config:
      prefix: calm
```

Important details:

- The runtime key is always `custom:<file_stem>`.
- The manifest `name` is display-only.
- Custom assertions can be used alongside built-in assertions in the same list.
- Custom assertions support the same `not-` negation prefix as built-in assertions.

See [Custom Assertions](/docs/evaluation/custom-assertions) for the manifest format, Python contract, params schema validation, context keys, and migration guidance.

## Negation with not- prefix

Any assertion type can be negated by prefixing it with `not-`. The engine inverts both the pass/fail boolean and the score (1.0 - original):

```yaml title="Negated assertion"
assertions:
  - type: not-contains
    value: "error"
  - type: not-contains-json
  - type: not-custom:blocked_word
    config:
      blocked: storm
```

Negation works for both built-in and custom assertion types.

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

## Execution model

Assertions do not share state with each other. Each configured assertion is evaluated independently against the same block result.

Runsight has two execution surfaces:

- Offline eval and other async callers use the shared async registry path, `run_assertions()`
- Live API block evaluation uses `EvalObserver` and the shared sync registry path, `run_assertions_sync()`

That means assertions are not always executed through the same concurrency model:

- Async registry callers can evaluate a block's assertions concurrently
- The live API `EvalObserver` path evaluates the block's assertions through the synchronous registry surface

In both paths:

- every configured assertion still gets its own result
- transform failures on one assertion do not prevent the rest of the list from producing results
- aggregate scoring still follows the same weighted scoring rules

## Assertion chaining

This is especially useful with `transform` hooks. Each assertion can target a different field in the block output using its own `json_path` transform:

```yaml title="Multiple assertions with different transforms"
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

In this example, the first assertion extracts `$.status` and checks for an exact match, the second extracts `$.message` and checks for a substring, and the third checks execution cost without any transform.

If a transform fails on one assertion (e.g., the output is not valid JSON, or the path does not exist), that assertion returns `passed=False` with a descriptive reason. The other assertions still run normally and produce their own results. The aggregate score and pass/fail are then computed across all of them using the standard [weighted scoring](#weighted-scoring) rules.

## How assertions fire during execution

When a workflow runs via the API, the engine wires assertions automatically:

1. `parse_workflow_yaml()` attaches each block's `assertions` to the runtime workflow
2. `ExecutionService._build_assertion_configs()` collects those assertion lists by block ID
3. `EvalObserver` receives the config map and watches block completion events
4. After a block completes, `EvalObserver.on_block_complete()`:
   - Extracts the block output from `WorkflowState`
   - Builds an `AssertionContext` with output, cost, latency, soul info, and tokens
   - Calls the shared sync registry path for that block's assertion list
   - Persists `eval_score`, `eval_passed`, and `eval_results` on the `RunNode` record
   - Emits a `node_eval_complete` SSE event

The `RunNode` entity stores three eval fields:

| Field | Type | Description |
|-------|------|-------------|
| `eval_score` | `Optional[float]` | Weighted average score across all assertions on the block |
| `eval_passed` | `Optional[bool]` | `True` when every individual assertion passed |
| `eval_results` | `Optional[Dict]` | Per-assertion results including pass/fail, score, reason, and handler type when the handler sets one |

These fields are `None` when a block has no assertions configured.

<!-- Linear: RUN-555, RUN-685, RUN-693, RUN-705, RUN-769, RUN-800, RUN-801 -- last verified against codebase 2026-04-10 -->
