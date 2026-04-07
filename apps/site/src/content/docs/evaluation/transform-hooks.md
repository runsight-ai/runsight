---
title: Transform Hooks
description: Pre-process block output before assertion evaluation using json_path transforms.
---

When a block produces structured output (like JSON), you often want to assert on a specific field rather than the entire output string. Transform hooks let you extract a sub-field before the assertion runs.

## Add a transform to an assertion

Set the `transform` field on any assertion config. The transform runs before the assertion evaluator sees the output:

```yaml title="custom/workflows/extract-check.yaml"
blocks:
  classify:
    type: llm
    soul_ref: classifier
    assertions:
      - type: contains-any
        value: ["positive", "negative", "neutral"]
        transform: "json_path:$.sentiment"
```

Without the transform, the `contains-any` assertion would check the entire LLM output string. With `transform: "json_path:$.sentiment"`, it checks only the extracted value of the `sentiment` field.

## json_path transform

The only supported transform type is `json_path`. The syntax is:

```
json_path:<JSONPath expression>
```

The engine:
1. Parses the block output as JSON (using `json.loads`)
2. Evaluates the JSONPath expression (using the `jsonpath_ng` library)
3. Extracts the first match
4. Converts the result to a string if it is not already one
5. Passes the extracted string to the assertion evaluator

### Supported JSONPath syntax

Runsight uses the `jsonpath_ng` library. Common patterns:

| Expression | Selects |
|-----------|---------|
| `$.field` | Top-level field |
| `$.nested.field` | Nested field |
| `$.items[0]` | First array element |
| `$.items[*].name` | `name` field from every array element (first match used) |
| `$..field` | Recursive descent -- finds `field` at any depth |

## Examples

### Check a sentiment label in a JSON response

```yaml title="Extract and assert on a JSON field"
blocks:
  analyze:
    type: llm
    soul_ref: analyst
    assertions:
      - type: contains-any
        value: ["bullish", "bearish", "neutral"]
        transform: "json_path:$.outlook"
```

If the block output is `{"outlook": "bullish", "confidence": 0.92}`, the assertion receives `"bullish"` and passes.

### Validate a nested score

```yaml title="Check a numeric field with equals"
blocks:
  scorer:
    type: llm
    soul_ref: evaluator
    assertions:
      - type: regex
        value: "^[1-5]$"
        transform: "json_path:$.rating"
```

If the block output is `{"rating": 4, "explanation": "Good quality"}`, the transform extracts `4`, converts it to the string `"4"`, and the regex assertion checks it.

### Combine with negation

Transforms work with negated assertion types:

```yaml title="Negated assertion with transform"
assertions:
  - type: not-contains
    value: "error"
    transform: "json_path:$.status"
```

## Error handling

The transform returns a failing `GradingResult` (score 0.0, passed false) in these cases:

| Condition | Reason message |
|-----------|----------------|
| Output is not valid JSON | `"Transform json_path failed: output is not valid JSON"` |
| JSONPath expression matches nothing | `"Transform json_path: path '<path>' not found in output"` |
| Unknown transform format (no `:` separator) | `"Unknown transform format: '<value>'"` |
| Unknown transform type (not `json_path`) | `"Unknown transform type: '<type>'"` |

When a transform fails, the assertion itself does not run. The failing `GradingResult` from the transform is used directly.

:::caution
The transform extracts only the **first match** from the JSONPath expression. If your path matches multiple values (e.g., `$.items[*].name`), only the first one is used for the assertion.
:::

<!-- Linear: RUN-695, RUN-685 -- last verified against codebase 2026-04-07 -->
