# runsight

**YAML-first workflow engine for AI agents.** Your workflows are files. Your repo is the database. Git is your version control.

[![license](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/runsight)](https://pypi.org/project/runsight/)
[![python](https://img.shields.io/badge/python-3.11+-blue)](https://www.python.org)
[![docs](https://img.shields.io/badge/docs-runsight.ai-orange)](https://runsight.ai/docs)

<p align="center">
  <img src="assets/demo.gif" alt="Runsight — visual workflow builder for AI agents" width="640">
</p>

Runsight runs AI agent workflows defined in plain YAML files on your filesystem. Every workflow, soul (agent identity), and tool definition is a diffable file in your repo. Save writes to disk. Commit pushes to git. Runs track which commit produced them. No database for workflow definitions — just files and git.

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

## Why Runsight

- Workflows are YAML files in your repo, so they stay diffable, reviewable, and versioned in Git.
- The GUI gives you a visual canvas and YAML editor over the same workflow state.
- Runs are traceable back to the workflow and commit that produced them.
- Built-in assertions, evals, and budget limits help you catch bad outputs and overspend early.
- Runsight is self-hosted and uses your keys, models, and infrastructure.

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
