---
title: Direct API Invocation
description: Reference for invoking Runsight workflows through the external Direct API.
---

Direct API invocation creates a production workflow run through an external HTTP request.
The requested workflow must exist in the committed `main` workflow snapshot and requires `enabled: true`.
Omitting `enabled` is treated the same as `enabled: false`, so a user must explicitly enable the workflow before it is externally invokable.

## Endpoint

```http
POST /api/workflows/{workflow_id}/runs
```

| Path parameter | Type | Required | Description |
|----------------|------|----------|-------------|
| `workflow_id` | string | Yes | Workflow ID to run. The server resolves the committed `main` workflow snapshot for this workflow and only invokes it when the snapshot has `enabled: true`. |

## Request body

The request body is required and strict. It must contain only `inputs`.

```json
{
  "inputs": {
    "topic": "quantum computing trends"
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `inputs` | object | Yes | Workflow input values. May be empty when the workflow has no required inputs. |

No other request body fields are accepted.

## Example request

```bash title="Invoke a workflow through the Direct API"
curl -X POST http://localhost:8000/api/workflows/research-pipeline/runs \
  -H "Content-Type: application/json" \
  -H "x-request-id: req_01HTZK7V9QK4K4Z8Z9J4Z4Z4Z4" \
  -d '{
    "inputs": {
      "topic": "quantum computing trends"
    }
  }'
```

The `x-request-id` header is optional. When present, Runsight records it as the run source correlation ID.

## Rejected request body fields

Direct API callers must not send privileged execution, provenance, delivery, simulation, or idempotency fields in the JSON body.

Examples of rejected fields:

| Field |
|-------|
| `workflow_id` |
| `source` |
| `branch` |
| `commit_sha` |
| `debug` |
| `simulation` |
| `simulation_id` |
| `simulation_branch` |
| `idempotency_key` |
| `idempotency_token` |
| `trigger` |
| `trigger_id` |
| `delivery` |
| `delivery_id` |
| `provenance` |
| `source_metadata` |
| `source_correlation_id` |
| `caller` |

Unsupported or privileged request body fields are rejected with `422 WORKFLOW_INPUT_VALIDATION_ERROR`.

## Success response

A successful Direct API invocation returns `200` with a `RunResponse`.

`200` means run creation or launch was accepted. Workflow execution continues in the background, and the run may later be pending, running, failed, or completed.

The response uses the server run response schema and includes the created run details, including server-authored values such as `source: "api"` and `branch: "main"`.

## Server-authored fields

Direct API always sets these run properties on the server.

| Property | Value | Caller-controlled |
|----------|-------|-------------------|
| `source` | `api` | No |
| `branch` | `main` | No |
| `source_metadata.entry_path` | `direct_api` | No |
| `source_metadata.request_path` | Request path | No |
| `source_correlation_id` | From request headers | Headers only |

## Correlation headers

Runsight reads correlation IDs from request headers.

| Header | Description |
|--------|-------------|
| `x-request-id` | Request correlation ID |
| `x-correlation-id` | Alternate request correlation ID |

`source_correlation_id` cannot be supplied in the request body.

## Workflow snapshot resolution

Direct API always resolves the committed `main` workflow snapshot and requires that snapshot to be enabled.

| Runtime asset | Resolution behavior |
|---------------|---------------------|
| Workflow YAML | Committed `main` snapshot with `enabled: true` |
| Nested workflow YAML | Committed `main` snapshot through the resolved git ref |
| Snapshot-capable workflow asset discovery | Receives the resolved git ref from the execution runtime |
| Provider settings | Live server runtime configuration |
| Server settings | Live server runtime configuration |
| API keys and credentials | Live server environment or configuration |

Dirty working tree edits to workflow YAML and nested workflow YAML are ignored by Direct API runs. Do not rely on dirty working tree edits for Direct API workflow definitions.

## Configuration

Environment variables use the `RUNSIGHT_` prefix.

| Setting | Default | Description |
|---------|---------|-------------|
| `RUNSIGHT_EXTERNAL_INVOCATION_ENABLED` | `true` | Enables external Direct API invocation. |
| `RUNSIGHT_PUBLIC_BASE_URL` | unset | Optional public base URL for external invocation contexts. |
| `RUNSIGHT_EXTERNAL_INVOCATION_BODY_LIMIT_BYTES` | `1048576` | Maximum Direct API request body size in bytes. |
| `RUNSIGHT_MAX_CONCURRENT_RUNS` | `5` | Maximum concurrent workflow runs. |
| `RUNSIGHT_MAX_PENDING_EXTERNAL_INVOCATIONS` | `32` | Maximum queued pending external invocations. |

## Host binding defaults

The default host is `127.0.0.1`.

:::caution
Runsight's self-hosted API is unauthenticated today. Keep host binding and Docker port publishing on loopback unless you intentionally expose the service behind your own proxy and authentication controls.
:::

Docker compose publishes the API on host loopback:

```yaml title="docker-compose.yml"
ports:
  - "127.0.0.1:8000:8000"
```

The Dockerfile command may bind to `0.0.0.0` inside the container. Host publishing examples should still bind to loopback unless you intentionally expose the service.

## Error responses

| Status | Code | Description |
|--------|------|-------------|
| `404` | `WORKFLOW_NOT_FOUND` | The workflow ID does not resolve to a workflow, or the committed `main` workflow snapshot is not enabled. |
| `413` | `REQUEST_BODY_TOO_LARGE` | The request body exceeds `RUNSIGHT_EXTERNAL_INVOCATION_BODY_LIMIT_BYTES`. |
| `422` | `WORKFLOW_INPUT_VALIDATION_ERROR` | The body shape is invalid, privileged fields are present, required inputs are missing, or input types do not match. |
| `429` | `ADMISSION_SATURATED` | Runtime admission limits are saturated. |
| `503` | `RUNTIME_UNAVAILABLE` | The workflow runtime is unavailable or external invocation is disabled. |

Direct API request and workflow input validation failures use `422`, not `400`.

## Idempotency

Direct API invocation in RUN-85 does not provide idempotency support.

| Input | Behavior |
|-------|----------|
| `x-idempotency-key` header | Not persisted, exposed, or used for deduplication |
| Request body idempotency fields | Rejected with `422 WORKFLOW_INPUT_VALIDATION_ERROR` |

## Redaction and metadata filtering

Runsight redacts sensitive workflow input values by omitting the value from stored and returned `workflow_inputs` payloads.

`source_metadata` is server-authored for Direct API runs. Unsafe metadata keys are rejected or dropped. Accepted responses, detail responses, list responses, and stored payloads must not leak authorization data, raw sensitive input values, or unsupported idempotency fields.

## Availability of other external sources

Webhook and schedule invocation are not part of RUN-85.

| Source | Availability |
|--------|--------------|
| `api` | Shipped production source |
| `manual` | Shipped production source |
| `webhook` | Not part of RUN-85 |
| `schedule` | Not part of RUN-85 |

<!-- Linear: RUN-943 — last verified against codebase 2026-04-26 -->
