---
title: Souls Overview
description: What souls are in Runsight — agent identities with role, prompt, provider, model, and tool bindings.
---

Every AI agent needs an identity: who it is, how it thinks, what model powers it, and which tools it can use. In Runsight, that identity is called a **soul**.

A soul is a standalone YAML file that defines an agent's persona, behavior constraints, model configuration, and tool access. Souls live in `custom/souls/` and are referenced by workflow blocks using the `soul_ref` field. This separation keeps agent identity independent from workflow logic — the same soul can power steps across many workflows, and changing a soul's prompt or model updates every workflow that uses it.

## Why souls exist

Workflow engines typically embed agent configuration inline — the prompt, model, and temperature live inside each workflow step. This creates three problems:

1. **Duplication.** The same "Senior Researcher" prompt appears in every workflow that uses it. A prompt revision means editing every copy.
2. **Coupling.** Changing which model an agent uses requires editing every workflow, not just the agent's configuration.
3. **No management surface.** There is no central place to see all agents, compare prompts, or track which workflows depend on a given agent.

Souls solve these by extracting agent identity into a standalone, reusable artifact. A soul file is the single source of truth for how an agent behaves, regardless of where it is used.

## Anatomy of a soul

A soul file is a YAML document with a flat structure. Here is a complete example:

```yaml title="custom/souls/researcher.yaml"
id: researcher
kind: soul
name: Researcher
role: Senior Researcher
system_prompt: |
  You are a senior research analyst. Given a topic, you produce
  a structured report with findings, sources, and confidence levels.
  Always cite your sources and flag low-confidence claims.
provider: openai
model_name: gpt-4o
temperature: 0.3
max_tokens: 4096
tools:
  - http
max_tool_iterations: 5
avatar_color: "#4f46e5"
```

### Required fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Embedded soul id. Must match the filename stem for external soul files. |
| `kind` | `"soul"` | Entity kind. Must be `"soul"`. |
| `name` | `str` | Display name for this soul. |
| `role` | `str` | The agent's role, displayed in the Soul Library UI. |
| `system_prompt` | `str` | The system instructions that define behavior and constraints. |

### Optional fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model_name` | `str` | `None` | Model to use (e.g., `gpt-4o`, `claude-sonnet-4`). Required for execution. |
| `provider` | `str` | `None` | Provider for the model (e.g., `openai`, `anthropic`). Required for execution. |
| `temperature` | `float` | `None` | Sampling temperature override. |
| `max_tokens` | `int` | `None` | Output token limit override. |
| `tools` | `list[str]` | `None` | Tool IDs this soul can use. Must be declared in the workflow's `tools:` section. |
| `required_tool_calls` | `list[str]` | `None` | Tool function names the LLM must call before completing. |
| `max_tool_iterations` | `int` | `5` | Maximum number of tool-use iterations per execution. |
| `avatar_color` | `str` | `None` | UI color hint for displaying the soul (hex or HSL). |

:::caution
Both `provider` and `model_name` must be set for a soul to execute at runtime. A soul with one but not the other will fail. There are no implicit default models.
:::

## How blocks reference souls

Workflow blocks reference souls through the `soul_ref` field. The value is the soul's embedded `id`.

```yaml title="custom/workflows/research.yaml"
version: "1.0"
id: research
kind: workflow
blocks:
  analyze:
    type: linear
    soul_ref: researcher
workflow:
  name: research_pipeline
  entry: analyze
  transitions:
    - from: analyze
      to: null
```

In this example, `soul_ref: researcher` resolves to the soul whose embedded id is `researcher`. For an external soul file, that means `custom/souls/researcher.yaml` must also contain `id: researcher`.

The following block types use `soul_ref`:

| Block Type | How it uses the soul |
|------------|---------------------|
| `linear` | Single LLM call using the soul's prompt and model. |
| `gate` | Quality-gate LLM call that evaluates output against criteria. |
| `dispatch` | Per-exit `soul_ref` on each exit definition — each branch gets its own soul. |

## Soul discovery and resolution

When the parser processes a workflow YAML file, it resolves souls in three steps:

1. **Discover external souls.** The parser scans `custom/souls/` for `.yaml` files, loads each into a `Soul` object, and rejects files whose embedded `id` does not match the filename stem. Only `.yaml` files are discovered — `.yml` files are ignored.

2. **Merge inline souls (if present).** If the workflow YAML contains an optional `souls:` section, those inline definitions are merged over the discovered external souls. When an inline soul has the same key as an external file, the inline definition wins and a warning is logged.

3. **Resolve `soul_ref` on each block.** Every block's `soul_ref` is looked up in the merged souls map. If the reference is not found, the parser raises a `ValueError` listing the available souls and suggesting the file to create.

Discovery runs exactly once per workflow parse, regardless of how many blocks reference souls. Multiple blocks can share the same `soul_ref`.

## One soul per step

Each workflow step is powered by exactly one soul. There are no multi-soul nodes or agent-debate patterns in the current architecture. If a workflow needs different perspectives, use separate steps with different souls connected by transitions:

```yaml title="custom/workflows/review.yaml"
version: "1.0"
id: review
kind: workflow
blocks:
  draft:
    type: linear
    soul_ref: writer
  review:
    type: gate
    soul_ref: editor
    eval_key: quality
workflow:
  name: draft_review
  entry: draft
  transitions:
    - from: draft
      to: review
    - from: review
      to: null
```

## Tool governance

Souls can declare which tools they need via the `tools` field. However, every tool a soul references must also appear in the workflow's top-level `tools:` whitelist. This two-layer design is intentional — it gives workflow authors explicit control over which tools are available in a given workflow, regardless of what individual souls request.

```yaml title="custom/souls/fetcher.yaml"
id: fetcher
kind: soul
name: Fetcher
role: Data Fetcher
system_prompt: Fetch and summarize data from URLs.
provider: openai
model_name: gpt-4o
tools:
  - http
```

```yaml title="custom/workflows/fetch_pipeline.yaml"
version: "1.0"
id: fetch_pipeline
kind: workflow
tools:
  - http
blocks:
  fetch:
    type: linear
    soul_ref: fetcher
workflow:
  name: fetch_pipeline
  entry: fetch
  transitions:
    - from: fetch
      to: null
```

If the soul declares `tools: [http]` but the workflow does not include `http` in its `tools:` section, the parser raises an error naming both the soul and the missing tool.

## Inline souls (DX shorthand)

For quick prototyping, souls can be defined inline within a workflow YAML file under the `souls:` section. The dictionary key must match the soul's `id` field:

```yaml title="custom/workflows/prototype.yaml"
version: "1.0"
id: prototype
kind: workflow
souls:
  drafter:
    id: drafter
    kind: soul
    name: Drafter
    role: Quick Drafter
    system_prompt: Draft a short summary.
    model_name: gpt-4o
    provider: openai
blocks:
  draft:
    type: linear
    soul_ref: drafter
workflow:
  name: prototype
  entry: draft
  transitions:
    - from: draft
      to: null
```

Inline souls are convenience sugar for iteration. The external library model (`custom/souls/` files) is the primary approach — it enables the Soul Library UI, dependency tracking, and reuse across workflows.

:::tip
When an inline soul has the same key as an external soul file, the inline definition takes precedence and a warning is logged. This lets you temporarily override a library soul for testing without modifying the shared file.
:::

## File structure

```
custom/
└── souls/
    ├── researcher.yaml
    ├── editor.yaml
    ├── fetcher.yaml
    └── summarizer.yaml
```

Soul files are plain YAML with no wrapper structure — the fields sit at the top level of the file. There is no `version:` or `soul:` envelope; the file content maps directly to the soul definition.

## What's next

- [Soul Files](/docs/souls/soul-files) — detailed reference for every field, constraints, and validation rules
- [Inline Souls](/docs/souls/inline-souls) — when and how to use inline definitions
- [Block Types](/docs/workflows/block-types) — which blocks use `soul_ref` and how

<!-- Linear: RUN-467, RUN-569, RUN-438, RUN-439, RUN-490, RUN-572, RUN-585 — last verified against codebase 2026-04-07 -->
