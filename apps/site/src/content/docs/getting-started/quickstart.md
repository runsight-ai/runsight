---
title: Quickstart
description: Get Runsight running and create your first AI agent workflow in under 5 minutes.
---

Runsight is a YAML-first workflow engine for AI agents. Your workflows are files. Your repo is the database. Git is your version control.

This guide walks you through installing Runsight, starting the development environment, and running your first workflow.

## Prerequisites

- **Python 3.11+** with [uv](https://docs.astral.sh/uv/) (recommended) or pip
- **Node.js 20+** with [pnpm](https://pnpm.io/)
- **Git**

## Install

```bash
git clone https://github.com/runsight-ai/runsight.git
cd runsight

# Backend
uv sync

# Frontend
pnpm install
```

## Start the development environment

Open two terminals:

```bash
# Terminal 1 — API server
uv run uvicorn runsight_api.main:app
```

```bash
# Terminal 2 — GUI
pnpm -C apps/gui dev
```

Open [http://localhost:5173](http://localhost:5173). The onboarding flow will walk you through API key setup.

## Create your first workflow

Create a workflow file at `custom/workflows/my-first-flow.yaml`:

```yaml
version: "1.0"
blocks:
  research:
    type: linear
    soul_ref: researcher
  write_summary:
    type: linear
    soul_ref: writer
  quality_review:
    type: gate
    soul_ref: reviewer
    eval_key: write_summary
workflow:
  name: Research & Review
  entry: research
  transitions:
    - from: research
      to: write_summary
    - from: write_summary
      to: quality_review
```

This workflow has three steps:
1. **research** — an LLM call using the `researcher` soul
2. **write_summary** — another LLM call using the `writer` soul
3. **quality_review** — a gate block that evaluates the summary output

## Create a soul

Souls are agent identities — each one defines a role, system prompt, provider, and model. Create a soul file at `custom/souls/researcher.yaml`:

```yaml
id: researcher_1
role: Senior Researcher
system_prompt: >
  You are an expert researcher. Given a topic, provide a concise,
  well-structured summary of the key findings, trends, and insights.
provider: openai
model: gpt-4.1-mini
```

Or define souls inline in the workflow itself:

```yaml
version: "1.0"
souls:
  researcher:
    id: researcher_1
    role: Senior Researcher
    system_prompt: >
      You are an expert researcher. Summarize key findings and trends.
    provider: openai
    model: gpt-4.1-mini
blocks:
  research:
    type: linear
    soul_ref: researcher
workflow:
  name: Quick Research
  entry: research
  transitions:
    - from: research
      to: null
```

## Run the workflow

1. Open the GUI at [http://localhost:5173](http://localhost:5173)
2. Your workflow appears in the workflow list (auto-discovered from `custom/workflows/`)
3. Click the workflow to open it in the visual canvas
4. Click **Run** to execute

The run detail view shows:
- Per-block execution status
- Output from each step
- Cost and token usage
- The exact YAML that executed (snapshotted per run)

## Block types

Runsight ships with 5 block types:

| Type | What it does |
|------|-------------|
| `linear` | Single LLM call through a soul |
| `gate` | LLM quality gate — evaluates another block's output |
| `code` | Execute Python or JavaScript |
| `loop` | Iterate over items with an inner block |
| `workflow` | Compose sub-workflows with parent-child run linkage |

## Add a custom tool

Tools are YAML files with canonical IDs. Create `custom/tools/slack_payload_builder.yaml`:

```yaml
version: "1.0"
type: custom
executor: python
name: Slack Payload Builder
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

Tools are discovered automatically. Enable them at the workflow level — souls only get tools that the workflow explicitly allows.

## What's next

- Edit workflows in the **visual canvas** with bi-directional YAML sync
- Add **assertions** to blocks for quality evaluation (`contains`, `regex`, `word-count`)
- Set **budget limits** on workflows and blocks (cost caps, timeouts)
- Use the **Monaco YAML editor** with schema autocomplete alongside the canvas
- Run **offline evals** with fixture mode — no LLM calls needed
