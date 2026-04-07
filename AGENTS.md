# AGENTS.md

Instructions for AI agents working on this codebase.

## Release Process

**Every PR that changes behavior must bump the version** in the root `pyproject.toml`.

The `version` field in `pyproject.toml` (repo root) is the **single source of truth**. When a PR merges to main and the version has changed, CI automatically:
1. Publishes both `runsight` and `runsight-core` to PyPI
2. Builds and pushes Docker image to GHCR
3. Creates a git tag `v{version}`

Do NOT create git tags manually. Do NOT modify version fields in `apps/api/pyproject.toml` or `packages/core/pyproject.toml` — CI handles those.

## Development Commands

```bash
# Install dependencies
uv sync                # Python
pnpm install           # Node

# Run dev servers
uv run runsight                    # API at http://localhost:8000
pnpm -C apps/gui dev               # GUI at http://localhost:5173

# Tests (NEVER run the full suite — target specific files)
uv run pytest apps/api/tests/test_specific_file.py -v
pnpm -C apps/gui test:unit -- --run path/to/test.test.ts

# Lint
pnpm run lint
```

## Architecture

- `packages/core/` — Pure Python engine (asyncio, Pydantic, zero web deps)
- `apps/api/` — FastAPI server (SQLModel, SSE streaming)
- `apps/gui/` — React 19 + Vite + ReactFlow + Monaco
- `packages/shared/` — Shared TypeScript types
- `packages/ui/` — Shared UI components (shadcn/ui)

## Key Rules

- Workflows, souls, and tools are YAML files on disk — git is the version control
- Main branch = production. Simulation branches for testing uncommitted changes.
- Styling: CVA + Tailwind + @theme tokens. No BEM, no mixing approaches.
- Never run full test suites (pytest or vitest) — they consume ~4GB each and hang the machine.
