# runsight

**YAML-first workflow engine for AI agents.** Your workflows are files. Your repo is the database. Git is your version control.

[![license](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/runsight)](https://pypi.org/project/runsight/)
[![python](https://img.shields.io/badge/python-3.11+-blue)](https://www.python.org)
[![docs](https://img.shields.io/badge/docs-runsight.ai-orange)](https://runsight.ai/docs)
[![GitHub stars](https://img.shields.io/github/stars/runsight-ai/runsight)](https://github.com/runsight-ai/runsight)

<!-- TODO: demo GIF — record with VHS once UI is stable -->

Runsight runs AI agent workflows defined in plain YAML files on your filesystem. Every workflow, soul (agent identity), and tool definition is a diffable file in your repo. Save writes to disk. Commit pushes to git. Runs track which commit produced them. No database for workflow definitions — just files and git.

32 shipped epics, 215+ tickets, 6 block types, built-in eval, and per-run budget enforcement.

## Quick start

```bash
uvx runsight
```

Open [http://localhost:8000](http://localhost:8000). Your YAML files in `custom/` are your workflows.

> Don't have `uv`? Install it first: `curl -LsSf https://astral.sh/uv/install.sh | sh`

Or use Docker:

```bash
docker run -p 8000:8000 -v $(pwd):/workspace ghcr.io/runsight-ai/runsight
```

**[Documentation](https://runsight.ai/docs)** · [GitHub Discussions](https://github.com/runsight-ai/runsight/discussions) · [Issues](https://github.com/runsight-ai/runsight/issues)

## What it does

| Feature | What you get |
|---|---|
| **YAML workflows** | Workflows are `.yaml` files on disk. Edit in any editor, diff in any tool, review in any PR. |
| **Git-native execution** | Save = write to disk. Commit = git commit to main. Dirty runs create simulation branches automatically. |
| **6 block types** | `linear` (LLM call), `gate` (LLM quality gate), `code` (Python), `loop` (iteration), `workflow` (sub-flow composition), `dispatch` (parallel branching) |
| **Dispatch branching** | The soul calls a `delegate` tool to pick an exit port — LLM-driven routing on any block with `exits` |
| **Soul library** | Agent identities as reusable YAML files or inline in the workflow. Role, system_prompt, provider, model, temperature, tools. Referenced by `soul_ref`. |
| **Custom tools** | Define tools as YAML files in `custom/tools/`. Canonical IDs are filename stems (e.g., `slack_payload_builder`). Discovered automatically. Workflows declare which tools are available — souls only get tools enabled at the workflow level. |
| **Visual canvas** | ReactFlow-based editor with bi-directional YAML sync. `[alpha]` |
| **Monaco YAML editor** | Syntax highlighting, live YAML validation — side by side with the canvas. |
| **Block-level eval** | Assertions on any block: `contains`, `regex`, `contains-json`, `word-count`. Transform hooks extract fields before asserting. |
| **Offline eval runner** | Define test cases in an `eval:` YAML section. Run them offline with fixture mode — no LLM calls needed. |
| **Budget enforcement** | `limits:` section on workflows and blocks. Cost caps (USD), timeouts (seconds), warn or kill modes. Enforced per LLM call. |
| **Run inspection** | Full run history with regressions. Fork recovery from failed runs. Historical YAML snapshot per run. |
| **Provider management** | CRUD for providers, model catalog, per-provider fallback targets, strict soul resolution. |
| **Sub-workflow composition** | `workflow` blocks execute child workflows with parent-child run linkage, on_error modes, and output mapping. |

## YAML examples

### Inline souls + custom tool wiring

Souls can be defined inline or as reusable library files. Tools are YAML files — workflows control which tools each soul can access:

```yaml
# custom/tools/slack_webhook.yaml — custom HTTP tool
version: "1.0"
type: custom
executor: request
name: Slack Webhook
description: Send a message to a Slack channel.
parameters:
  type: object
  properties:
    payload_json:
      type: string
  required: [payload_json]
request:
  method: POST
  url: "${SLACK_WEBHOOK_URL}"
  headers:
    Content-type: application/json
  body_template: "{{ payload_json }}"
```

```yaml
# custom/tools/slack_payload_builder.yaml — custom Python tool
version: "1.0"
type: custom
executor: python
name: Slack Payload Builder
description: Build a JSON payload string for the Slack incoming webhook.
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

```yaml
# Workflow with inline soul + tool governance
version: "1.0"
souls:
  notifier:
    id: notifier_1
    role: Slack Reporter
    system_prompt: >
      Summarize the input and post it to Slack.
    tools:
      - slack_payload_builder
      - slack_webhook       # workflow must also enable these tools
    provider: openai
    model_name: gpt-4.1-mini
blocks:
  notify:
    type: linear
    soul_ref: notifier
workflow:
  name: Slack Notification
  entry: notify
  transitions:
    - from: notify
      to: null
```

## How it works

1. **Define** — Write workflows, souls, and tools as YAML files in `custom/workflows/`, `custom/souls/`, and `custom/tools/`. The engine discovers them by convention.
2. **Parse** — The engine validates YAML against Pydantic schemas, resolves `soul_ref` to library souls, discovers tools by canonical ID, and enforces tool governance (souls only get tools enabled at the workflow level).
3. **Execute** — `execute_block()` runs each block through a unified lifecycle: observer events, retry handling, exit handle routing, budget enforcement via `contextvars`.
4. **Observe** — Assertions evaluate per-block. `BudgetSession` tracks cost/tokens/time with parent propagation. SSE streams node completion status to the GUI. `[WIP: canvas live updates]`
5. **Version** — Every save writes to disk. Commits go to main. Simulation runs create branches. Run detail shows the exact YAML that executed.

## Architecture

```
runsight/
├── packages/core/          # Pure Python engine — asyncio, Pydantic
│   └── src/runsight_core/
│       ├── blocks/         # Linear, Gate, Code, Loop, Workflow, Dispatch
│       ├── yaml/           # Schema models, parser, validator
│       ├── budget_enforcement.py
│       └── eval/           # Assertions, eval runner, transforms
├── apps/api/               # FastAPI server — SQLModel, SSE streaming
│   └── src/runsight_api/
└── apps/gui/               # React 19 + Vite + ReactFlow + Monaco
    └── src/
        ├── features/       # Canvas, flows, runs, settings, souls
        └── store/          # Zustand stores
```

**Core engine** has zero web dependencies — import `runsight_core` and run workflows from Python:

```python
from runsight_core.yaml.parser import parse_workflow_yaml
from runsight_core.workflow import Workflow

workflow = parse_workflow_yaml("path/to/workflow.yaml")
result = await workflow.run(initial_state)
```

## Roadmap

Runsight is a **single-soul-per-step** workflow engine with sub-workflow composition. Next up: triggers (webhook, cron), MCP integration, runtime controls (pause/resume/kill), and OpenTelemetry export. See the [full roadmap](https://runsight.ai/docs) for details.

## Tech stack

| Layer | Stack |
|---|---|
| **Core engine** | Python 3.11+, asyncio, Pydantic, LiteLLM |
| **API server** | FastAPI, SQLModel, SSE |
| **Frontend** | React 19, Vite (build + dev server), ReactFlow (XY Flow), Monaco Editor, Zustand, shadcn/ui, Tailwind |
| **Storage** | Filesystem (YAML) for workflows/souls/tools, SQLite for settings |
| **Testing** | Playwright (E2E), Vitest (unit), pytest-asyncio (engine) |

## Development

```bash
git clone https://github.com/runsight-ai/runsight.git
cd runsight

# Install dependencies
uv sync              # Python 3.11+
pnpm install         # Node 20+ (installs all workspace packages)

# Start API server + GUI (two terminals)
uv run runsight                        # http://localhost:8000
pnpm -C apps/gui dev                   # http://localhost:5173
```

## Contributing

Issues and PRs welcome. See the [issues page](https://github.com/runsight-ai/runsight/issues) for open work. Questions and ideas go to [Discussions](https://github.com/runsight-ai/runsight/discussions).

```bash
# Run frontend unit tests
pnpm -C apps/gui test:unit

# Run engine tests (target specific files — full suite is heavy)
uv run python -m pytest packages/core/tests/test_specific_file.py -v

# Lint
pnpm run lint
```

## Releasing

Version is controlled by a single field: `version` in the root `pyproject.toml`. To publish a new release:

1. Bump `version` in `pyproject.toml` (e.g., `0.1.7` → `0.1.8`)
2. Merge to main
3. CI detects the version change → publishes PyPI + Docker → creates git tag `v0.1.8`

No manual tagging needed. Every PR that changes behavior should include a version bump.

## License

Apache 2.0 — see [LICENSE](LICENSE).
