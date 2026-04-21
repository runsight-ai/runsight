# runsight

**YAML-first workflow engine for AI agents.** Build multi-step agent workflows as files, run them locally, and inspect every run in a GUI.

[![PyPI](https://img.shields.io/pypi/v/runsight)](https://pypi.org/project/runsight/)
[![docs](https://img.shields.io/badge/docs-runsight.ai-orange)](https://runsight.ai/docs)
[![GitHub stars](https://img.shields.io/github/stars/runsight-ai/runsight)](https://github.com/runsight-ai/runsight)
[![license](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Powered by cubic.dev](https://img.shields.io/badge/powered%20by-cubic.dev-111111)](https://www.cubic.dev/)

<p align="center">
  <img src="assets/demo.gif" alt="Runsight — visual workflow builder for AI agents" width="640">
</p>

Runsight keeps workflow definitions in your repo instead of a hosted database. Workflows, souls, and tools live as YAML files on disk, while the app gives you a visual canvas, a YAML editor, reusable agent identities, custom tools, assertions, and run history tied to the workflow version that produced each result.

**[Documentation](https://runsight.ai/docs)** · [GitHub Discussions](https://github.com/runsight-ai/runsight/discussions) · [Issues](https://github.com/runsight-ai/runsight/issues)

## Install

```bash
uvx runsight
```

Open [http://localhost:8000](http://localhost:8000). Your YAML files in `custom/` are your workflows.

> Don't have `uv`? Install it first: `curl -LsSf https://astral.sh/uv/install.sh | sh`

Or use Docker:

```bash
docker run -p 8000:8000 -v $(pwd):/workspace ghcr.io/runsight-ai/runsight
```

## Quick start

```bash
# Start Runsight in the current repo
uvx runsight
```

Open [http://localhost:8000](http://localhost:8000). Your workflow files live in `custom/workflows/`, `custom/souls/`, and `custom/tools/`.

## What it does

| Capability | What you get |
|---|---|
| **Repo-native workflows** | Review workflows as `.yaml` files in PRs instead of chasing state hidden in a hosted builder or database. |
| **Visual canvas + YAML editor** | Move between drag-and-drop editing and raw YAML without splitting the source of truth. |
| **Souls and tool governance** | Reuse agent identities, lock workflows to approved tools, and keep model/provider choices explicit. |
| **Assertions and evals** | Catch missing sections, regex failures, fixture regressions, and output drift close to the workflow itself. |
| **Git-aware execution** | Tie runs back to the workflow version and commit that produced them, including simulation-branch flows when the repo is dirty. |
| **Budget and limits** | Warn or stop runs when they exceed spend or timeout thresholds instead of discovering it after the fact. |
| **Dispatch and sub-workflows** | Route across exits with model decisions and compose larger systems from smaller workflows. |

## Example workflow

```yaml
version: "1.0"
id: summarize
kind: workflow
souls:
  writer:
    id: writer
    kind: soul
    name: Writer
    role: Technical Writer
    system_prompt: >
      Summarize the input into a short release note.
    provider: openai
    model_name: gpt-4.1-mini
blocks:
  summarize:
    type: linear
    soul_ref: writer
workflow:
  name: Summarize
  entry: summarize
```

## How it works

1. **Define** — Write workflows, souls, and tools as YAML files under `custom/`.
2. **Edit** — Use the GUI canvas or the YAML editor against the same workflow state on disk.
3. **Execute** — Run the workflow locally with provider/model settings, tool access, assertions, and limits applied.
4. **Inspect** — Review outputs, costs, regressions, and the exact workflow version and commit that produced a run.

## Contributing

New contributors are welcome. Questions and ideas go to [Discussions](https://github.com/runsight-ai/runsight/discussions), and open work lives on [Issues](https://github.com/runsight-ai/runsight/issues).

Local setup:

```bash
git clone https://github.com/runsight-ai/runsight.git
cd runsight

uv sync              # Python 3.11+
pnpm install         # Node 20+

uv run runsight                        # http://localhost:8000
pnpm -C apps/gui dev                   # http://localhost:5173
```

Targeted checks:

```bash
pnpm -C apps/gui test:unit
uv run python -m pytest packages/core/tests/test_specific_file.py -v
pnpm run lint
```

If your PR changes behavior, bump the root `pyproject.toml` version. CI handles publishing and tagging after merge to `main`.

## License

Apache 2.0 — see [LICENSE](LICENSE).
