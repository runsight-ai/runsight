---
title: Built-in Tools
description: Reference for the three tools that ship with Runsight — delegate, http, and file_io.
---

Runsight ships with three built-in tools. They are always available and do not require any files in `custom/tools/`. Use their canonical ID directly in your workflow and soul `tools` lists.

## `delegate`

Routes execution to an exit port. When a soul calls `delegate`, it picks which branch of the workflow to follow next. This is the mechanism behind LLM-driven branching.

See [Dispatch & Delegate](/docs/tools/dispatch-and-delegate) for the full explanation of how delegate and dispatch work together.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `port` | `str` | Yes | The exit port ID to delegate to. Must match one of the block's declared `exits[].id` values. |
| `task` | `str` | Yes | The task instruction to delegate to this port. |

When the block has exits defined, the `port` parameter is constrained to an enum of valid exit IDs. The LLM sees the valid options and picks one.

### How it works

1. A block declares `exits` -- a list of named ports
2. The soul assigned to that block has `delegate` in its `tools` list
3. At runtime, the LLM calls the `delegate` tool with `{"port": "some_exit", "task": "..."}`
4. The runner captures the `port` value as the block's `exit_handle`
5. The workflow engine uses `exit_handle` to look up the next block via `conditional_transitions`

### Return value

The delegate tool returns a JSON string `{"port": "<port>", "task": "<task>"}` on success. If the port is not in the valid set, it returns an error message listing valid ports.

### Usage example

```yaml title="custom/workflows/triage.yaml"
version: "1.0"
id: triage
kind: workflow
tools:
  - delegate
souls:
  router:
    id: router
    kind: soul
    name: Router
    role: Triage Router
    system_prompt: >
      Read the incoming request and route it to the correct team
      using the delegate tool.
    tools:
      - delegate
blocks:
  triage:
    type: linear
    soul_ref: router
    exits:
      - id: billing
        label: Billing Team
      - id: technical
        label: Technical Support
  handle_billing:
    type: linear
    soul_ref: billing_agent
  handle_technical:
    type: linear
    soul_ref: tech_agent
workflow:
  name: Support Triage
  entry: triage
  conditional_transitions:
    - from: triage
      billing: handle_billing
      technical: handle_technical
```

## `http`

Makes outbound HTTP requests to external URLs. Use this when a soul needs to fetch data from or send data to an external API at runtime, without defining a custom tool.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `method` | `str` | Yes | HTTP method (`GET`, `POST`, `PUT`, `DELETE`, etc.). |
| `url` | `str` | Yes | The target URL. |
| `headers` | `object` | No | Key-value mapping of HTTP headers. |
| `body` | `str` | No | Request body content. |
| `response_path` | `str` | No | Dot-notation path to extract from a JSON response. |

### Response handling

The response is processed based on the `Content-Type` header:

| Content-Type | Handling |
|-------------|----------|
| `application/json` | Parsed as JSON. If `response_path` is set, the value at that path is extracted. |
| `text/html` | Converted to readable plain text (scripts and styles stripped). |
| `text/plain` | Returned as-is. |

Responses larger than 64 KB are truncated.

:::note
The `http` tool validates URLs against SSRF (Server-Side Request Forgery) before making requests.
:::

### Usage example

```yaml title="custom/workflows/lookup.yaml"
version: "1.0"
id: lookup
kind: workflow
tools:
  - http
souls:
  fetcher:
    id: fetcher
    kind: soul
    name: Fetcher
    role: Data Fetcher
    system_prompt: >
      Fetch the requested data using the http tool and summarize the results.
    tools:
      - http
blocks:
  fetch_data:
    type: linear
    soul_ref: fetcher
workflow:
  name: API Lookup
  entry: fetch_data
```

The LLM decides at runtime what URL to call, what method to use, and what headers to send. The tool result is returned to the LLM as part of the agentic tool loop.

## `file_io`

Reads and writes files within a sandboxed base directory. Path traversal and absolute paths are rejected.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `action` | `str` (enum: `read`, `write`) | Yes | Whether to read or write. |
| `path` | `str` | Yes | Relative file path within the sandbox directory. |
| `content` | `str` | No | Content to write. Only used when `action` is `write`. |

### Security constraints

- **No absolute paths** -- paths like `/etc/passwd` are rejected with a `PermissionError`
- **No path traversal** -- paths containing `..` are rejected
- **Sandbox boundary** -- the resolved path must stay within the configured base directory
- On write, parent directories are created automatically if they do not exist

### Return value

- **Read**: returns the file content as a string
- **Write**: returns a confirmation message with the byte count (e.g., `"Written 42 bytes to output/report.txt"`)

### Usage example

```yaml title="custom/workflows/report.yaml"
version: "1.0"
id: report
kind: workflow
tools:
  - file_io
souls:
  writer:
    id: writer
    kind: soul
    name: Writer
    role: Report Writer
    system_prompt: >
      Write the analysis report to a file using the file_io tool.
    tools:
      - file_io
blocks:
  write_report:
    type: linear
    soul_ref: writer
workflow:
  name: Report Generation
  entry: write_report
```

<!-- Linear: RUN-273 (Tool Registry epic) — last verified against codebase 2026-04-07 -->
