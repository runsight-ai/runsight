---
title: Assertion Reference
description: All 15 assertion types with their parameters, plus the not- prefix and json_path transform hook.
---

<!-- RUN-695 -->

Assertions validate block outputs against expected values. They are used in the `assertions` field on any block and in the `eval` section's `expected` entries. Each assertion is a dict with at minimum a `type` field.

## Assertion config fields

Every assertion config supports these fields:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | `str` | -- | Assertion type name (see sections below). Prefix with `not-` to negate. |
| `value` | `Any` | `""` | Comparison value (type-specific) |
| `threshold` | `float` | varies | Pass threshold (type-specific) |
| `weight` | `float` | `1.0` | Weight for aggregated scoring |
| `metric` | `str` | none | Named score key for tracking |
| `transform` | `str` | none | Pre-processing transform (see [Transform hooks](#transform-hooks)) |

---

## String assertions

### equals

Exact string match or JSON deep-equal. Tries JSON parsing first; falls back to string comparison.

| Parameter | Type | Description |
|-----------|------|-------------|
| `value` | `Any` | Expected value (string or JSON) |

```yaml
- type: equals
  value: "expected output"
```

### contains

Case-sensitive substring check.

| Parameter | Type | Description |
|-----------|------|-------------|
| `value` | `str` | Substring to find |

```yaml
- type: contains
  value: "machine learning"
```

### icontains

Case-insensitive substring check.

| Parameter | Type | Description |
|-----------|------|-------------|
| `value` | `str` | Substring to find (case-insensitive) |

```yaml
- type: icontains
  value: "Machine Learning"
```

### contains-all

All items in the value list must be present as substrings.

| Parameter | Type | Description |
|-----------|------|-------------|
| `value` | `List[str]` | List of substrings that must all be present |

```yaml
- type: contains-all
  value: ["introduction", "methodology", "conclusion"]
```

### contains-any

At least one item in the value list must be present as a substring.

| Parameter | Type | Description |
|-----------|------|-------------|
| `value` | `List[str]` | List of candidate substrings |

```yaml
- type: contains-any
  value: ["approved", "accepted", "passed"]
```

### starts-with

String prefix check.

| Parameter | Type | Description |
|-----------|------|-------------|
| `value` | `str` | Expected prefix |

```yaml
- type: starts-with
  value: "Summary:"
```

### regex

Regex search match (uses `re.search`, not full match).

| Parameter | Type | Description |
|-----------|------|-------------|
| `value` | `str` | Regular expression pattern |

```yaml
- type: regex
  value: "\\d{4}-\\d{2}-\\d{2}"
```

### word-count

Word count check. Supports exact count or min/max range.

| Parameter | Type | Description |
|-----------|------|-------------|
| `value` | `int` or `{min, max}` | Exact word count, or a dict with optional `min` and `max` bounds |

```yaml
# Exact count
- type: word-count
  value: 100

# Range
- type: word-count
  value:
    min: 50
    max: 200
```

---

## Structural assertions

### is-json

Validates that the output is valid JSON. Optionally validates against a JSON Schema.

| Parameter | Type | Description |
|-----------|------|-------------|
| `value` | `Dict` (JSON Schema) or `null` | Optional JSON Schema to validate against |

```yaml
# Just check valid JSON
- type: is-json

# With schema validation
- type: is-json
  value:
    type: object
    required: ["title", "body"]
    properties:
      title:
        type: string
      body:
        type: string
```

### contains-json

Finds a valid JSON substring in the output. Scans for `{` and `[` delimiters and attempts to parse. Optionally validates the extracted JSON against a JSON Schema.

| Parameter | Type | Description |
|-----------|------|-------------|
| `value` | `Dict` (JSON Schema) or `null` | Optional JSON Schema to validate extracted JSON against |

```yaml
- type: contains-json
  value:
    type: object
    required: ["status"]
```

---

## Linguistic assertions

### levenshtein

Edit distance between the output and a reference string must be at or below the threshold.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `value` | `str` | `""` | Reference string to compare against |
| `threshold` | `float` | `5` | Maximum allowed edit distance |

```yaml
- type: levenshtein
  value: "expected text"
  threshold: 10
```

### bleu

BLEU-4 score against a reference string must be at or above the threshold. Uses smoothing method 1 (add-one).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `value` | `str` | `""` | Reference text |
| `threshold` | `float` | `0.5` | Minimum BLEU score |

```yaml
- type: bleu
  value: "The expected reference text for comparison."
  threshold: 0.4
```

### rouge-n

ROUGE-1 F-measure against a reference string must be at or above the threshold. Uses the `rouge-score` library.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `value` | `str` | `""` | Reference text |
| `threshold` | `float` | `0.75` | Minimum ROUGE-N score |

```yaml
- type: rouge-n
  value: "The reference summary text."
  threshold: 0.6
```

---

## Performance assertions

### cost

Checks that the block's `cost_usd` is within the threshold. Reads from `AssertionContext.cost_usd`, not from the output string.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `threshold` | `float` | `0.0` | Maximum cost in USD |

```yaml
- type: cost
  threshold: 0.50
```

### latency

Checks that the block's `latency_ms` is within the threshold. Reads from `AssertionContext.latency_ms`, not from the output string.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `threshold` | `float` | `0.0` | Maximum latency in milliseconds |

```yaml
- type: latency
  threshold: 5000
```

---

## Negation prefix

Any assertion type can be negated by prefixing with `not-`. The result is inverted: `passed` becomes `not passed`, and `score` becomes `1.0 - score`.

```yaml
- type: not-contains
  value: "error"

- type: not-is-json
```

---

## Transform hooks

Transforms pre-process the block output before the assertion evaluates it. Specified via the `transform` field on any assertion config.

### json_path

Extracts a value from JSON output using JSONPath syntax (via the `jsonpath-ng` library). The extracted value is converted to a string and passed to the assertion.

Format: `json_path:<expression>`

```yaml
- type: contains
  value: "active"
  transform: "json_path:$.status"

- type: equals
  value: "42"
  transform: "json_path:$.data.count"
```

If the output is not valid JSON or the path is not found, the assertion fails with a descriptive error before the actual assertion runs.

---

## Scoring and aggregation

Assertions are scored and aggregated using weighted averages:

- Each assertion produces a `GradingResult` with `passed` (bool) and `score` (0.0--1.0).
- Weights default to `1.0` and are used for the weighted average (`aggregate_score`).
- In eval mode, the suite passes if `aggregate_score >= threshold` (default threshold: `1.0`).
- Without a threshold, all individual assertions must pass.

### Using in eval cases

```yaml title="eval section with assertions"
eval:
  threshold: 0.8
  cases:
    - id: test_summary
      fixtures:
        summarize: "Machine learning is a subset of AI that enables systems to learn."
      expected:
        summarize:
          - type: contains
            value: "machine learning"
          - type: word-count
            value:
              min: 5
              max: 50
          - type: not-contains
            value: "error"
```

### Using on blocks

```yaml title="block-level assertions"
blocks:
  research:
    type: linear
    soul_ref: researcher
    assertions:
      - type: is-json
      - type: word-count
        value:
          min: 100
```
