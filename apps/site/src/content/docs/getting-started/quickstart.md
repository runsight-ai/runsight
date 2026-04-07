---
title: Quickstart
description: Install Runsight and run your first AI agent workflow in under 5 minutes.
---

## Install

```bash
uvx runsight
```

Open [http://localhost:8000](http://localhost:8000). The onboarding flow walks you through API key setup.

Don't have `uv`? Install it first: `curl -LsSf https://astral.sh/uv/install.sh | sh`

### Docker

```bash
docker run -p 8000:8000 -v $(pwd):/workspace ghcr.io/runsight-ai/runsight
```

## Create your first workflow

Create a file at `custom/workflows/my-first-flow.yaml`:

```yaml
version: "1.0"
blocks:
  research:
    type: linear
    soul_ref: researcher
  write_summary:
    type: linear
    soul_ref: writer
    depends: research
  quality_review:
    type: gate
    soul_ref: reviewer
    eval_key: write_summary
    depends: write_summary
workflow:
  name: Research & Review
  entry: research
```

Three steps: **research** calls an LLM, **write_summary** runs next, and **quality_review** evaluates the output.

## Create a soul

Souls are agent identities. Create `custom/souls/researcher.yaml`:

```yaml
id: researcher_1
role: Senior Researcher
system_prompt: >
  You are an expert researcher. Given a topic, provide a concise,
  well-structured summary of the key findings, trends, and insights.
provider: openai
model: gpt-4.1-mini
```

Create `writer` and `reviewer` souls the same way, each with their own role and prompt.

## Run it

1. Open the GUI at [http://localhost:8000](http://localhost:8000)
2. Your workflow appears in the **Flows** page (auto-discovered from `custom/workflows/`)
3. Click the workflow to open it in the canvas
4. Click **Run**

## What's next

- [Key Concepts](/docs/getting-started/key-concepts) — understand blocks, souls, tools, and dispatch
- [Block Types](/docs/workflows/block-types) — the 5 block types and when to use each
- [Custom Tools](/docs/tools/custom-tools) — define tools as YAML files
- [Assertions & Eval](/docs/evaluation/assertions) — add quality checks to your workflows
- [Git Integration](/docs/execution/git-integration) — how save, commit, and simulation branches work
