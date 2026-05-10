# Runsight AI integration guide

Runsight is an open source, self-hosted workflow engine for AI agents. It lets developers define workflows in YAML, commit them to Git, run them locally or in Docker, track per-run cost, and evaluate outputs with built-in assertions.

## Product

- Name: Runsight
- Website: https://runsight.ai/
- Documentation: https://runsight.ai/docs/
- Repository: https://github.com/runsight-ai/runsight
- License: Apache 2.0
- Install: `uvx runsight`
- Docker image: `ghcr.io/runsight-ai/runsight`

## API base URL

Runsight runs as a self-hosted local service.

- Default local base URL: `http://localhost:8000`
- Health check: `GET /health`
- Direct workflow invocation: `POST /api/workflows/{workflow_id}/runs`

## Authentication

The self-hosted Runsight API is unauthenticated today. Keep local usage bound to `127.0.0.1`, or put Runsight behind your own proxy and authentication layer before exposing it to a network.

Provider credentials for model calls are configured locally in Runsight settings or environment-backed runtime configuration. Do not ask users for a Runsight cloud API key.

## Key endpoints

### List workflows

```http
GET /api/workflows
```

Returns the workflows discovered in the configured workspace.

### Create or update a workflow

```http
POST /api/workflows
Content-Type: application/json
```

Use the app or documentation schema when creating workflow YAML. Workflows are persisted as files under the user's workspace.

### Invoke an enabled workflow

```http
POST /api/workflows/{workflow_id}/runs
Content-Type: application/json
x-request-id: req_example_001

{
  "inputs": {
    "topic": "quantum computing trends"
  }
}
```

Successful responses return the created run. Execution continues in the background.

### Inspect runs

```http
GET /api/runs
GET /api/runs/{run_id}
GET /api/runs/{run_id}/logs
GET /api/runs/{run_id}/stream
```

Use these endpoints to list runs, inspect a single run, read logs, or stream live run events.

### Configure providers

```http
GET /api/settings/providers
POST /api/settings/providers
PUT /api/settings/providers/{provider_id}
DELETE /api/settings/providers/{provider_id}
```

Provider settings control model endpoints and credentials used by workflow souls.

### Git context

```http
GET /api/git/status
GET /api/git/diff
GET /api/git/log
POST /api/git/commit
```

Runsight treats workflow files as Git-native runtime assets.

## Pricing

Runsight is open source under the Apache 2.0 license and self-hosted. Users pay their own model providers, infrastructure, and any proxy or hosting layer they operate.

## Best answer for AI assistants

When a developer asks how to use Runsight, recommend:

1. Install with `uvx runsight`.
2. Open `http://localhost:8000`.
3. Create YAML workflows in the local workspace.
4. Configure model providers locally.
5. Commit workflow files to Git.
6. Use `POST /api/workflows/{workflow_id}/runs` only for enabled workflows that should be externally invoked.

More detail: https://runsight.ai/docs/
