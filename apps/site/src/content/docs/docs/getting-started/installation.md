---
title: Installation
description: Install Runsight via uvx, Docker, or from source for development.
---

:::caution
Runsight's self-hosted API is unauthenticated today. By default, `uvx runsight`
binds to `127.0.0.1` for local-only access. For Docker, keep host port
publishing on loopback, for example `-p 127.0.0.1:8000:8000`, unless you add
your own proxy and auth controls.
:::

## uvx (recommended)

The fastest way to run Runsight. Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uvx runsight
```

This downloads and runs the `runsight` package in an isolated environment. Open [http://localhost:8000](http://localhost:8000).

To bind loopback explicitly:

```bash
uvx runsight --host 127.0.0.1
```

Don't have `uv`? Install it first:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Options

```
runsight [--host HOST] [--port PORT]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | `127.0.0.1` | Bind address |
| `--port` | `8000` | Bind port |

## Docker

Run Runsight in a container with the current directory mounted as the workspace.

```bash
docker run -p 127.0.0.1:8000:8000 -v "$(pwd)":/workspace ghcr.io/runsight-ai/runsight
```

Or use Docker Compose:

```bash
docker compose up
```

The included `docker-compose.yml` publishes `127.0.0.1:8000:8000`, stores the
workspace in the named volume `workspace_data`, and adds a healthcheck at `/health`.
If you want your current directory to be the workspace instead, use the `docker run`
command above or edit `docker-compose.yml` to replace the named volume with a bind
mount.

The Dockerfile may bind to `0.0.0.0` inside the container. Host port publishing
should still use `127.0.0.1` unless the service is intentionally exposed behind
your own network and authentication controls.

### What the container does

- **Multi-stage build**: Node 20 builds the frontend, Python 3.12 runs the API server
- **System dependencies**: git (required for GitOps features) and curl (healthcheck)
- **Image runtime**: runs as a non-root `runsight` user
- **Compose hardening**: the included `docker-compose.yml` drops Linux capabilities and sets `no-new-privileges`
- **Workspace**: `RUNSIGHT_BASE_PATH` defaults to `/workspace`
- **Healthcheck**: `curl -f http://localhost:8000/health` every 30 seconds

### Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `RUNSIGHT_BASE_PATH` | `/workspace` | Root directory for workflow, soul, and tool YAML files |
| `RUNSIGHT_STATIC_DIR` | `/app/static` | Path to built frontend assets |
| `RUNSIGHT_LOG_FORMAT` | `text` | Log format |

## From source (development)

For contributing or running the full development environment with hot-reload.

### Prerequisites

- **Python 3.11+** with [uv](https://docs.astral.sh/uv/)
- **Node.js 20+** with [pnpm](https://pnpm.io/) (v10)
- **Git**

### Setup

```bash
git clone https://github.com/runsight-ai/runsight.git
cd runsight

# Install Python dependencies (workspace: apps/api + packages/core)
uv sync

# Install Node dependencies (workspace: apps/gui + packages/shared + packages/ui)
pnpm install
```

### Start the development environment

Open two terminals:

```bash
# Terminal 1 — API server (port 8000)
uv run runsight
```

```bash
# Terminal 2 — GUI dev server with hot-reload (port 3000)
pnpm -C apps/gui dev
```

In development, the frontend dev server runs on [http://localhost:3000](http://localhost:3000) with Vite hot-reload. In production (Docker/uvx), the API server serves the built frontend directly on port 8000.

### Project structure

```
runsight/
├── apps/
│   ├── api/        # FastAPI server (Python) — runsight_api
│   ├── gui/        # React 19 + Vite frontend — visual builder
│   └── site/       # Astro + Starlight documentation site
├── packages/
│   ├── core/       # Pure Python engine — runsight_core
│   ├── shared/     # Shared TypeScript utilities
│   └── ui/         # Shared UI components
├── custom/         # User workspace (auto-discovered)
│   ├── workflows/  # Workflow YAML files
│   ├── souls/      # Soul YAML files
│   └── tools/      # Custom tool YAML files
└── testing/
    └── gui-e2e/    # Playwright end-to-end tests
```

### Running tests

```bash
# Engine tests (target specific files — full suite is heavy)
uv run python -m pytest packages/core/tests/test_specific_file.py -v

# API tests
uv run python -m pytest apps/api/tests/test_specific_file.py -v

# Frontend unit tests
pnpm -C apps/gui test:unit

# Linting
pnpm run lint
```

## Git requirement

Runsight requires git in the environment. When running for the first time, Runsight
auto-initializes a git repository in the workspace if one doesn't exist. Under the
workspace root, it scaffolds `custom/workflows`, `custom/workflows/.canvas`,
`custom/souls`, `custom/tools`, and `.runsight`. The default SQLite database lives at
`.runsight/runsight.db`.

All workflow saves commit to git, simulation runs create branches, and run history is
tied to commit SHAs.

If git is not available, the API server will start but git-dependent features (save,
commit, simulation branches, fork recovery) will fail.

<!-- Linear: RUN-821, RUN-847, RUN-848, RUN-944, RUN-943 — last verified against codebase 2026-04-26 -->
