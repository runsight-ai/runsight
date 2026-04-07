---
title: Custom Tools
description: Complete YAML reference for custom tools — Python executor, HTTP request executor, parameters schema, discovery rules, and reserved IDs.
---

Custom tools are YAML files in `custom/tools/` that define capabilities a soul can invoke during execution. Each file describes one tool with its executor type, parameters, and implementation.

## File format

Every custom tool YAML file has these required fields:

| Field | Type | Description |
|-------|------|-------------|
| `version` | `str` | Schema version. Must be `"1.0"`. |
| `type` | `str` | Must be `"custom"`. |
| `executor` | `str` | `"python"` or `"request"`. |
| `name` | `str` | Human-readable tool name. |
| `description` | `str` | What the tool does. Sent to the LLM as the function description. |
| `parameters` | `object` | JSON Schema object describing the tool's input parameters. |

Additionally, depending on the executor:

| Executor | Required | Optional |
|----------|----------|----------|
| `python` | `code` or `code_file` (exactly one) | -- |
| `request` | `request` mapping | `timeout_seconds` |

The canonical tool ID is derived from the filename stem. A file at `custom/tools/sentiment.yaml` has ID `sentiment`.

:::caution
The `description` field is required. Discovery will reject any tool file that omits it or provides an empty string.
:::

## Python executor

The Python executor runs your code in a sandboxed subprocess. The tool receives arguments as JSON on stdin and returns the result on stdout.

Your code must define a `def main(args)` function. The `args` parameter is a dictionary matching the `parameters` schema.

### Inline code

```yaml title="custom/tools/sentiment.yaml"
version: "1.0"
type: custom
executor: python
name: sentiment_analyzer
description: Analyze the sentiment of the given text and return a score.
parameters:
  type: object
  properties:
    text:
      type: string
      description: The text to analyze.
  required:
    - text
code: |
  def main(args):
      text = args["text"]
      positive_words = ["good", "great", "excellent", "love"]
      score = sum(1 for w in text.lower().split() if w in positive_words)
      return {"sentiment": "positive" if score > 0 else "neutral", "score": score}
```

### External code file

For longer implementations, use `code_file` to reference a Python file in the same directory as the YAML:

```yaml title="custom/tools/data_processor.yaml"
version: "1.0"
type: custom
executor: python
name: data_processor
description: Process and transform structured data records.
parameters:
  type: object
  properties:
    records:
      type: array
      items:
        type: object
  required:
    - records
code_file: data_processor.py
```

```python title="custom/tools/data_processor.py"
def main(args):
    records = args["records"]
    processed = [{"id": r.get("id"), "status": "done"} for r in records]
    return {"processed": processed, "count": len(processed)}
```

:::note
You cannot declare both `code` and `code_file` on the same tool. The parser rejects this as an error.
:::

### Python executor constraints

- The `code` (or contents of `code_file`) must define exactly `def main(args)` with a single parameter named `args`
- The function's return value is serialized as JSON and sent back to the LLM
- The subprocess runs with a minimal environment (`PATH`, `HOME` only)
- Python executor tools cannot declare `request`, `timeout_seconds`, or any HTTP-related fields

## HTTP request executor

The request executor makes an outbound HTTP call. Use this for integrating with external APIs without writing Python code.

```yaml title="custom/tools/slack_notify.yaml"
version: "1.0"
type: custom
executor: request
name: slack_notify
description: Send a notification message to a Slack channel via webhook.
parameters:
  type: object
  properties:
    message:
      type: string
      description: The message to send.
  required:
    - message
timeout_seconds: 10
request:
  method: POST
  url: "${SLACK_WEBHOOK_URL}"
  headers:
    Content-Type: application/json
  body_template: '{"text": "{{ message }}"}'
```

### Request fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `method` | `str` | Yes | HTTP method (`GET`, `POST`, `PUT`, `DELETE`, etc.). Defaults to `GET` if omitted. |
| `url` | `str` | Yes | The target URL. Supports `${ENV_VAR}` for environment variable substitution. |
| `headers` | `object` | No | Key-value mapping of HTTP headers. Values support `${ENV_VAR}` substitution. |
| `body_template` | `str` | No | Request body. Supports `{{ param }}` for parameter substitution and `${ENV_VAR}` for secrets. |
| `response_path` | `str` | No | Dot-notation path to extract from a JSON response (e.g., `data.result`). |

### Template syntax

Two template syntaxes are available in `url`, `headers`, `body_template`, and `response_path`:

- **`{{ param }}`** -- substitutes a value from the tool's `args` dictionary
- **`${ENV_VAR}`** -- substitutes an environment variable value (raises an error if the variable is not set)

### Request executor constraints

- Request executor tools cannot declare `code` or `code_file`
- The `request` mapping is required and must contain at least `url`
- Only these fields are allowed in the `request` mapping: `method`, `url`, `headers`, `body_template`, `response_path`
- `timeout_seconds` is optional and must be a positive integer

### Response handling

The response is processed based on the `Content-Type` header:

| Content-Type | Handling |
|-------------|----------|
| `application/json` | Parsed as JSON. If `response_path` is set, the value at that path is extracted. |
| `text/html` | Converted to readable text (scripts, styles, and hidden tags are stripped). |
| `text/plain` | Returned as-is. |
| Other | Returned as text. |

Responses larger than 64 KB are truncated with a `[truncated]` suffix.

## Parameters schema

The `parameters` field uses JSON Schema format. This schema is sent to the LLM as the function parameter definition and is used to validate arguments at call time.

```yaml
parameters:
  type: object
  properties:
    query:
      type: string
      description: The search query.
    limit:
      type: integer
      description: Maximum number of results.
  required:
    - query
```

The `description` on each property helps the LLM understand what to pass. Always include descriptions for non-obvious parameters.

## Discovery rules

1. Only `.yaml` files in `custom/tools/` are scanned (not subdirectories)
2. The canonical ID is the filename without the `.yaml` extension
3. Duplicate IDs (same filename stem) are rejected
4. All required fields must be present and non-empty strings
5. Unknown fields are rejected (the allowed set is: `version`, `type`, `executor`, `name`, `description`, `parameters`, `code`, `code_file`, `request`, `timeout_seconds`)
6. The `type` field must be `"custom"`

## Reserved IDs

The following IDs are reserved for builtin tools and cannot be used as custom tool filenames:

- `http`
- `file_io`
- `delegate`

Creating a file named `custom/tools/http.yaml` will cause a parse error.

## Using a custom tool in a workflow

To make a custom tool available, declare it in both the workflow's `tools` list and the soul's `tools` list:

```yaml title="custom/workflows/analysis.yaml"
version: "1.0"
tools:
  - sentiment
souls:
  analyst:
    id: analyst
    role: Sentiment Analyst
    system_prompt: Analyze the sentiment of the provided text using the sentiment tool.
    tools:
      - sentiment
blocks:
  analyze:
    type: linear
    soul_ref: analyst
workflow:
  name: Sentiment Analysis
  entry: analyze
```

Both layers are required. See [Tools Overview](/docs/tools/overview) for details on the governance model.

<!-- Linear: RUN-273 (Tool Registry epic) — last verified against codebase 2026-04-07 -->
