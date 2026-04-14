---
title: Key Concepts
description: Core primitives in Runsight — workflows, blocks, souls, tools, and dispatch.
---

Runsight has five core primitives: **workflows**, **blocks**, **souls**, **tools**, and **dispatch**. Everything is defined in YAML files on your filesystem. Git is the version control layer.

## Workflows

A workflow is a YAML file in `custom/workflows/` that defines a directed graph of blocks. The engine discovers workflow files automatically.

```yaml
version: "1.0"
id: research-pipeline
kind: workflow
blocks:
  research:
    type: linear
    soul_ref: researcher
  summarize:
    type: linear
    soul_ref: writer
    depends: research
workflow:
  name: Research Pipeline
  entry: research
```

A workflow file has these top-level sections:

| Section | Default | Purpose |
|---------|---------|---------|
| `version` | `"1.0"` | Schema version |
| `blocks` | `{}` | Block definitions keyed by block ID |
| `workflow` | **required** | Graph metadata — `name`, `entry` block, and `transitions` |
| `souls` | `{}` | Inline soul definitions (optional shorthand) |
| `tools` | `[]` | Tool IDs available to this workflow |
| `limits` | none | Budget constraints (cost caps, timeouts) |
| `eval` | none | Test cases for offline evaluation |
| `enabled` | `false` | Whether the workflow is active |
| `interface` | none | Public input/output contract for callable sub-workflows |
| `config` | `{}` | Arbitrary workflow configuration |

Only `workflow` is required — all other sections have defaults.

Workflows are **nestable** — a `workflow` block can execute another workflow file as a child, with parent-child run linkage and independent error handling.

## Blocks

Blocks are the execution units inside a workflow. Each block has a `type` that determines its behavior. Runsight ships with six block types:

| Type | What it does |
|------|-------------|
| `linear` | Single LLM call through a soul. The most common block type. |
| `gate` | LLM quality gate — evaluates another block's output and routes on pass/fail. |
| `code` | Runs Python code. Define a `def main(data)` function in the `code` field. |
| `loop` | Iterates inner blocks for up to `max_rounds` rounds with optional break conditions. |
| `workflow` | Executes a child workflow via `workflow_ref`. Parent-child run linkage, `on_error` modes. |
| `dispatch` | Parallel branching — each exit port gets its own soul and task instruction. All branches execute concurrently. |

All blocks share a unified execution lifecycle via `execute_block()`:

1. Observer notified (`on_block_start`)
2. Block-scoped budget session created (if `limits` defined)
3. Retry wrapper applied (if `retry_config` defined)
4. Timeout enforced via `asyncio.wait_for`
5. Block executes
6. Exit conditions evaluated — sets the `exit_handle` for downstream routing
7. Observer notified (`on_block_complete`)

Blocks can define `assertions` for quality evaluation, `exits` for multi-path routing, `depends` for dependency ordering, and `error_route` for error-specific branching.

## Souls

A soul is an agent identity — it defines who an LLM is and how it behaves. Souls are YAML files in `custom/souls/`:

```yaml
# custom/souls/researcher.yaml
id: researcher
kind: soul
name: Researcher
role: Senior Researcher
system_prompt: >
  You are an expert researcher. Given a topic, provide a concise,
  well-structured summary of key findings, trends, and insights.
provider: openai
model_name: gpt-4.1-mini
temperature: 0.7
max_tokens: 2048
```

Soul fields:

| Field | Required | Purpose |
|-------|----------|---------|
| `id` | Yes | Unique identifier |
| `kind` | Yes | Entity kind, always `soul` |
| `name` | Yes | Display name |
| `role` | Yes | Agent role label |
| `system_prompt` | Yes | LLM system instructions |
| `provider` | No | LLM provider (e.g., `openai`, `anthropic`) |
| `model_name` | No | Model name (e.g., `gpt-4.1-mini`). Falls back to runner default if omitted. |
| `temperature` | No | Sampling temperature |
| `max_tokens` | No | Output token limit |
| `tools` | No | Tool names this soul can use |
| `avatar_color` | No | UI display color |
| `max_tool_iterations` | No | Max tool-use loops per execution (default: 5) |

Blocks reference souls via `soul_ref`:

```yaml
blocks:
  research:
    type: linear
    soul_ref: researcher  # resolves by embedded soul id
```

Souls can also be defined inline in the workflow YAML as optional shorthand — see [Inline Souls](/docs/souls/inline-souls).

**One soul per step.** Each block references at most one soul. The exception is `dispatch`, where each exit port has its own soul.

## Tools

Tools are capabilities that souls can use during execution. They come in three types:

- **Built-in tools**: Ship with Runsight — `delegate` (exit port routing), `http` (outbound requests), `file_io` (file operations)
- **Custom tools**: YAML files in `custom/tools/` with a Python or HTTP executor
- **HTTP tools**: Declarative HTTP request definitions

Custom tool example:

```yaml
# custom/tools/slack_payload_builder.yaml
version: "1.0"
id: slack_payload_builder
kind: tool
type: custom
executor: python
name: Slack Payload Builder
description: Builds a Slack message payload from plain text.
parameters:
  type: object
  properties:
    text:
      type: string
  required: [text]
code: |
  import json
  def main(args):
      return {"payload_json": json.dumps({"text": args["text"]})}
```

Custom tools are identified by their embedded `id`, and the YAML filename stem must match that id. Built-in tools use reserved IDs: `delegate`, `http`, `file_io`.

Tools are discovered automatically from `custom/tools/`.

**Tool governance** is enforced at the workflow level: a soul only gets access to tools that the workflow explicitly lists in its `tools` section. Both the workflow and the soul must declare the tool for it to be available during execution.

## Dispatch

Dispatch is the branching mechanism. There are two ways to branch in Runsight:

### Exit ports on any block

Any block can define `exits`. When a soul lists `delegate` in its tools and the workflow enables it, the soul can call `delegate(port="...", task="...")` to pick which exit port to route to — making the LLM the decision-maker.

```yaml
blocks:
  triage:
    type: linear
    soul_ref: triager
    exits:
      - id: urgent
        label: Urgent — needs immediate attention
      - id: normal
        label: Normal — standard processing
  handle_urgent:
    type: linear
    soul_ref: responder
    depends: triage
  handle_normal:
    type: linear
    soul_ref: processor
    depends: triage
```

The `delegate` tool requires two parameters: `port` (constrained to the declared exit IDs) and `task` (instruction for the downstream block). The soul must list `delegate` in its `tools` array, and the workflow must include `delegate` in its top-level `tools` list.

### Dispatch block (parallel branching)

The `dispatch` block type runs all branches concurrently — each exit port gets its own soul and task instruction. Unlike exit ports on a `linear` block (where the LLM picks one), dispatch executes every branch.

See [Dispatch & Delegate](/docs/tools/dispatch-and-delegate) for details.

## Process Isolation

Every LLM block runs in an isolated subprocess. The subprocess has no API keys, no access to engine memory, and no credentials. All LLM calls are proxied through a Unix socket IPC channel where the engine holds the real keys, enforces budget limits, and records observability traces.

This is transparent --- you don't configure it. Workflow YAML and block behavior are identical whether isolation is enabled or not. The isolation layer protects against prompt injection, model misbehavior, and credential leakage.

See [Process Isolation](/docs/execution/process-isolation) for the full architecture.

## YAML-First, Git-Native

Everything in Runsight is a file:

| Primitive | Location | Format |
|-----------|----------|--------|
| Workflows | `custom/workflows/*.yaml` | YAML |
| Souls | `custom/souls/*.yaml` | YAML |
| Tools | `custom/tools/*.yaml` | YAML |

Git is the version control layer:

- **Save** writes the workflow YAML to disk and commits to the `main` branch
- **Dirty runs** (unsaved changes) automatically create **simulation branches** (`sim/{workflow-slug}/{YYYYMMDD}/{short-id}`)
- Every run records the **commit SHA** of the workflow that executed
- **Fork recovery** lets you branch from a failed run to iterate without losing history
- The run detail view shows the **historical YAML snapshot** — the exact file content that ran, not the current version

There is no database for workflow definitions. Your repo is the database. Diff your workflows, review them in PRs, roll back with git.
