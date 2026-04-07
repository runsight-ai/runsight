---
title: Soul Files
description: Complete field reference for soul YAML files — every field, type, default, and constraint.
---

import { FileTree } from '@astrojs/starlight/components';

Soul files are standalone YAML documents stored in `custom/souls/`. Each file defines one agent identity. There is no envelope or wrapper structure — the soul fields sit at the top level of the file.

## File location and naming

<FileTree>
- custom/
  - souls/
    - researcher.yaml
    - editor.yaml
    - fetcher.yaml
</FileTree>

The **filename stem** (the part before `.yaml`) is the soul's lookup key. When a workflow block sets `soul_ref: researcher`, the parser resolves it to `custom/souls/researcher.yaml`.

Only `.yaml` files are discovered. Files with the `.yml` extension are ignored. Files whose names start with `_` are not excluded — all `.yaml` files in the directory are loaded.

## File format

A soul file is flat YAML with no version field and no wrapping key. The file content maps directly to the soul definition:

```yaml title="custom/souls/researcher.yaml"
id: researcher_v1
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
avatar_color: accent
```

## Field reference

### Required fields

These fields must be present in every soul file. The parser raises a `ValidationError` if any are missing.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique identifier for this soul. Can differ from the filename stem. |
| `role` | `str` | The agent's role (e.g., "Senior Researcher"). Displayed as the soul name in the UI. |
| `system_prompt` | `str` | System instructions defining the agent's behavior and constraints. |

### Optional fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model_name` | `str` | `None` | Model identifier (e.g., `gpt-4o`, `claude-sonnet-4`). Falls back to the runner's default if not set. |
| `provider` | `str` | `None` | Provider for the model (e.g., `openai`, `anthropic`). Falls back to the runner's default if not set. |
| `temperature` | `float` | `None` | Sampling temperature override. When `None`, uses the model's default. |
| `max_tokens` | `int` | `None` | Output token limit override. When `None`, uses the model's default. |
| `tools` | `list[str]` | `None` | Tool IDs this soul can use. Each must also be declared in the workflow's top-level `tools:` section. |
| `required_tool_calls` | `list[str]` | `None` | LLM-facing tool function names that must be called before the agent completes. |
| `max_tool_iterations` | `int` | `5` | Maximum number of tool-use iterations per execution. |
| `avatar_color` | `str` | `None` | UI color for displaying the soul. Accepts one of six preset tokens: `accent`, `info`, `success`, `warning`, `danger`, `neutral`. |

:::caution
Both `provider` and `model_name` should be set for a soul to execute at runtime. A soul with one but not the other will fall back to the runner's defaults for the missing value.
:::

## `id` vs filename stem

The `id` field and the filename stem are independent. A file named `researcher.yaml` can contain `id: researcher_v1`. Workflow blocks reference the **filename stem** (`soul_ref: researcher`), not the internal `id`.

The `id` field is used by the engine at runtime to identify the soul object. The filename stem is the lookup key during YAML parsing and discovery.

## Validation rules

Soul files are validated using Pydantic's `model_validate`. The schema model (`SoulDef` in `schema.py`) enforces:

- **`extra="forbid"`** — unknown fields raise a validation error. Only the fields listed above are accepted.
- **Required fields** — `id`, `role`, and `system_prompt` must be present. A missing field produces a Pydantic `ValidationError`.
- **Type checking** — each field must match its declared type. A string where an integer is expected raises a validation error.

There are no `ge`, `le`, or `min_length` constraints on soul fields. The `max_tool_iterations` field accepts any integer.

## `soul_ref` resolution

When the parser encounters a `soul_ref` on a block, it resolves the reference through these steps:

1. **Discover external souls.** The parser calls `_discover_souls()`, which scans `custom/souls/` for `.yaml` files. Each file is loaded, validated against the `Soul` model, and stored in a dictionary keyed by filename stem.

2. **Merge inline souls.** If the workflow YAML contains a `souls:` section, inline definitions are merged over the external map. When keys overlap, the inline soul wins and a warning is logged: `"Inline soul 'X' overrides external soul file"`.

3. **Look up `soul_ref`.** The block's `soul_ref` value is looked up in the merged map. If not found, the parser raises a `ValueError` listing available souls.

## Tool governance

A soul's `tools` list declares which tools the agent needs, but every listed tool must also appear in the workflow's top-level `tools:` section. If a soul references a tool not declared in the workflow, the parser raises a `ValueError`:

```
Soul 'fetcher' (custom/souls/fetcher.yaml) references undeclared tool 'http'.
Declared tools: []
```

This two-layer design gives workflow authors explicit control over which tools are available in a given workflow, regardless of what individual souls request.

## `modified_at` field

The `modified_at` field is set by the API server when a soul is created or updated through the GUI. It stores a Unix timestamp (float). This field is not part of the engine's runtime `Soul` model — it is metadata tracked by the API layer for display in the Soul Library's "Modified" column.

## What's next

- [Souls Overview](/docs/souls/overview) — concepts, architecture, and design rationale
- [Inline Souls](/docs/souls/inline-souls) — defining souls directly inside workflow YAML
- [Soul Library](/docs/souls/soul-library) — managing souls through the GUI

<!-- Linear: RUN-467, RUN-437, RUN-443 — Soul Management project (bb749057) — last verified against codebase 2026-04-07 -->
