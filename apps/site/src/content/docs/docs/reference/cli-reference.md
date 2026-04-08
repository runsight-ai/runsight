---
title: CLI Reference
description: Command-line interface for the Runsight server — runsight command, options, and Docker usage.
---

<!-- RUN-110 -->

The `runsight` command starts the Runsight server (FastAPI + Uvicorn). The CLI is intentionally minimal -- it launches the server and serves the bundled GUI.

## Running with uvx

The recommended way to run Runsight is via `uvx`, which handles Python package resolution automatically:

```bash
uvx runsight
```

This installs the `runsight` package (if not already cached) and runs the `runsight` entry point, which is registered in `pyproject.toml` as:

```
[project.scripts]
runsight = "runsight_api.cli:main"
```

## Command syntax

```
runsight [--host HOST] [--port PORT]
```

## Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--host` | `str` | `0.0.0.0` | Bind address for the server |
| `--port` | `int` | `8000` | Bind port for the server |
| `--help`, `-h` | -- | -- | Print usage information and exit |

Unknown arguments cause the CLI to print an error and exit with code 1.

## Examples

```bash
# Start with defaults (0.0.0.0:8000)
uvx runsight

# Custom port
uvx runsight --port 3000

# Bind to localhost only
uvx runsight --host 127.0.0.1 --port 9000
```

On startup, the CLI prints:

```
  Runsight running at http://localhost:8000
  Press Ctrl+C to stop
```

## Docker

Runsight ships a multi-stage Dockerfile that bundles the frontend and backend into a single image.

```bash
# Build the image
docker build -t runsight .

# Run with defaults
docker run -p 8000:8000 runsight

# Mount a workspace directory for your workflows, souls, and tools
docker run -p 8000:8000 -v $(pwd)/custom:/workspace/custom runsight
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RUNSIGHT_BASE_PATH` | `/workspace` | Root path for workflow discovery |
| `RUNSIGHT_STATIC_DIR` | `/app/static` | Path to the bundled frontend assets |
| `RUNSIGHT_LOG_FORMAT` | `text` | Log output format |

The container exposes port `8000` and includes a health check at `/health`.

### Passing CLI flags in Docker

The default Docker `CMD` is `["runsight"]`. Override it to pass flags:

```bash
docker run -p 3000:3000 runsight runsight --port 3000
```

## Requirements

- Python >= 3.11
- The `runsight` package installs FastAPI, Uvicorn, SQLModel, and all other dependencies automatically.
