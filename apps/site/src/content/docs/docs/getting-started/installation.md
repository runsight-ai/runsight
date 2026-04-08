---
title: Installation
description: Install Runsight via uvx, Docker, or from source for development.
---

## uvx (recommended)

The fastest way to run Runsight. Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uvx runsight
```

This downloads and runs the `runsight` package in an isolated environment. Open [http://localhost:8000](http://localhost:8000).

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
| `--host` | `0.0.0.0` | Bind address |
| `--port` | `8000` | Bind port |

## Docker

Run Runsight in a container with the current directory mounted as the workspace.

```bash
docker run -p 8000:8000 -v $(pwd):/workspace ghcr.io/runsight-ai/runsight
```

Or use Docker Compose:

```bash
docker compose up
```

The included `docker-compose.yml` mounts the current directory at `/workspace`, exposes port 8000, and adds a healthcheck at `/health`.

### What the container does

- **Multi-stage build**: Node 20 builds the frontend, Python 3.12 runs the API server
- **System dependencies**: git (required for GitOps features) and curl (healthcheck)
- **Workspace**: `RUNSIGHT_BASE_PATH` defaults to `/workspace`. If no volume is mounted, a warning is printed and data won't persist when the container stops.
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
# Terminal 2 — GUI dev server with hot-reload (port 5173)
pnpm -C apps/gui dev
```

In development, the frontend dev server runs on [http://localhost:5173](http://localhost:5173) with Vite hot-reload. In production (Docker/uvx), the API server serves the built frontend directly on port 8000.

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

Runsight requires git in the environment. When running for the first time, Runsight auto-initializes a git repository in the workspace if one doesn't exist. All workflow saves commit to git, simulation runs create branches, and run history is tied to commit SHAs.

If git is not available, the API server will start but git-dependent features (save, commit, simulation branches, fork recovery) will fail.
