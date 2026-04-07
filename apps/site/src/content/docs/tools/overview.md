---
title: Tools Overview
description: What tools are in Runsight, the three types (builtin, custom, HTTP), canonical IDs, discovery, and the two-layer governance model.
---

Tools give souls the ability to take action beyond generating text. When a soul has tools, the LLM enters an agentic tool loop: it can call tools, read their results, and decide what to do next -- all within a single block execution.

## Three tool types

Runsight supports three kinds of tools:

| Type | Where it lives | How it runs |
|------|---------------|-------------|
| **Builtin** | Ships with Runsight | Native async Python |
| **Custom (Python)** | `custom/tools/*.yaml` | Sandboxed subprocess |
| **Custom (HTTP)** | `custom/tools/*.yaml` | Outbound HTTP request |

**Builtin tools** are part of the Runsight engine. Three ship today: `delegate`, `http`, and `file_io`. See [Built-in Tools](/docs/tools/built-in-tools) for details on each.

**Custom tools** are YAML files you create in `custom/tools/`. Each file defines a tool with either a `python` executor (inline code or a `code_file` reference) or a `request` executor (outbound HTTP). See [Custom Tools](/docs/tools/custom-tools) for the full YAML format.

## Canonical IDs

Every tool has a **canonical ID** -- a plain string used everywhere: workflow YAML, soul definitions, resolution, and runtime. The canonical ID is:

- For **builtin tools**: the reserved string itself -- `delegate`, `http`, or `file_io`
- For **custom tools**: the YAML filename stem -- a file at `custom/tools/sentiment.yaml` has canonical ID `sentiment`

IDs are plain strings with no prefix. You write `delegate` in your YAML, not `builtin/delegate`.

```yaml title="custom/workflows/example.yaml"
tools:
  - delegate
  - http
  - sentiment
```

:::caution
Custom tool filenames must not collide with reserved builtin IDs. If you create `custom/tools/http.yaml`, the parser will reject it with an error.
:::

The three reserved builtin tool IDs are: `http`, `file_io`, and `delegate`.

## Discovery

Custom tools are discovered automatically from `custom/tools/*.yaml` at parse time. The discovery engine:

1. Scans `custom/tools/` for `.yaml` files
2. Derives the canonical ID from each filename stem
3. Validates that no custom ID collides with reserved builtin IDs
4. Validates all required fields (`version`, `type`, `executor`, `name`, `description`, `parameters`)
5. For Python executors, validates that the code defines `def main(args)`
6. For request executors, validates the `request` mapping (method, url, etc.)

No registration step is needed. Drop a valid YAML file into `custom/tools/` and it is available to any workflow that declares it.

## Two-layer governance

Tools in Runsight use a two-layer governance model. Both layers must agree before a soul can use a tool at runtime.

### Layer 1: Soul declares tools

Each soul lists the tools it wants to use in its `tools` field:

```yaml title="custom/souls/router.yaml"
id: router
role: Router Agent
system_prompt: Route the task to the correct team.
tools:
  - delegate
```

This is the soul's declaration of intent. It says "I need access to the `delegate` tool."

### Layer 2: Workflow whitelists tools

The workflow file has a top-level `tools` list that acts as a whitelist:

```yaml title="custom/workflows/triage.yaml"
version: "1.0"
tools:
  - delegate
  - http
```

Only tools listed here can be used by any soul in this workflow.

### Governance validation

At parse time, Runsight checks every soul referenced by the workflow. For each tool in a soul's `tools` list, it verifies that the tool appears in the workflow's `tools` whitelist. If a soul references a tool that the workflow does not declare, parsing fails with an error:

```
Soul 'router' (custom/souls/router.yaml) references undeclared tool 'http'.
Declared tools: ['delegate']
```

This two-layer model ensures that workflow authors control which tools are available, while soul authors declare which tools they need.

## How tools bind to souls at parse time

During workflow parsing (step 6.6 in the parser), tools are resolved and attached to souls:

1. **Governance validation** runs first -- every soul's tool references are checked against the workflow whitelist
2. **Definition validation** confirms that every declared tool ID is resolvable (either a known builtin or a discovered custom tool with valid metadata)
3. **Tool resolution** creates `ToolInstance` objects for each tool. For the `delegate` tool, the parser finds the block that references the soul and passes the block's `exits` list so the delegate tool knows which exit ports are valid
4. **Binding** attaches the resolved `ToolInstance` objects to `soul.resolved_tools`, making them available to the agentic tool loop at runtime

The tool loop in the runner then uses `soul.resolved_tools` to build the OpenAI function-calling schema and execute tool calls as the LLM requests them.

<!-- Linear: RUN-273 (Tool Registry epic) — last verified against codebase 2026-04-07 -->
