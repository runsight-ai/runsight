---
title: Error Handling
description: error_route, on_error modes, retry_config, and how errors propagate through the workflow execution lifecycle.
---

Runsight provides three mechanisms for handling errors in workflows: `error_route` for redirecting execution after a block failure, `on_error` for controlling sub-workflow failure behavior, and `retry_config` for automatic retry with backoff.

## error_route

The `error_route` field on any block redirects execution to a specific block when an error occurs, instead of failing the entire workflow.

```yaml title="custom/workflows/error-example.yaml"
blocks:
  risky_step:
    type: linear
    soul_ref: analyst
    error_route: fallback_step
  fallback_step:
    type: linear
    soul_ref: writer
```

### How error_route works

When a block with `error_route` raises an exception:

1. The exception is caught by the workflow's main execution loop.
2. A `BlockResult` is created for the failed block with `exit_handle: "error"` and the error details stored in metadata (`error_type`, `error_message`, `block_id`).
3. The error info is also written to `shared_memory` under `__error__{block_id}`.
4. The execution queue is cleared and replaced with the error route target.
5. Execution continues from the error route block.

The error route block can read the error details from shared memory:

```yaml title="Accessing error context in the fallback block"
blocks:
  risky_step:
    type: linear
    soul_ref: analyst
    error_route: handle_error
  handle_error:
    type: linear
    soul_ref: error_handler
```

The `handle_error` block's soul can access `__error__risky_step` in shared memory, which contains `{"type": "...", "message": "..."}`.

### Soft-error routing

Error routing also activates for **soft errors** --- blocks that complete normally but produce a `BlockResult` with `exit_handle: "error"`. This happens when a `workflow` block uses `on_error: "catch"` and the child workflow fails. The parent block completes (no exception raised), but its result signals an error. If the parent block has an `error_route`, execution is redirected.

:::note
The `error_route` field must reference a block that exists in the workflow. The parser validates this during workflow construction, and the runtime validates it again before execution.
:::

## on_error (workflow blocks)

The `on_error` field is specific to `workflow` blocks (type: `"workflow"`). It controls what happens when a child workflow fails.

| Value | Behavior |
|-------|----------|
| `"raise"` | **Default.** The child's exception propagates to the parent. The parent block fails, and normal error handling applies (error_route if set, otherwise the parent workflow fails). |
| `"catch"` | The exception is swallowed. The parent block completes with `exit_handle: "error"` and a `BlockResult` containing the child error details. Execution continues from the parent. |

```yaml title="Catch mode example"
blocks:
  optional_enrichment:
    type: workflow
    workflow_ref: enrichment-pipeline
    on_error: catch
    error_route: skip_enrichment
    inputs:
      topic: "shared_memory.topic"
    outputs:
      "shared_memory.enriched": summary
  skip_enrichment:
    type: linear
    soul_ref: writer
```

In this example:
1. If `enrichment-pipeline` fails, the exception is caught (`on_error: "catch"`).
2. The `optional_enrichment` block completes with `exit_handle: "error"`.
3. Because `error_route` is set, execution redirects to `skip_enrichment`.
4. The workflow continues instead of failing.

### Soft error detection in catch mode

When `on_error: "catch"` is set, the workflow block also detects soft errors in the child's results. If any child block produced a `BlockResult` with `exit_handle: "error"` (even without raising an exception), the parent block treats this as a failure and returns an error `BlockResult`. This prevents silently swallowing errors that were caught by error_route within the child workflow.

## retry_config

The `retry_config` field adds automatic retry with configurable backoff to any block.

```yaml title="Retry example"
blocks:
  flaky_api_call:
    type: linear
    soul_ref: analyst
    retry_config:
      max_attempts: 3
      backoff: exponential
      backoff_base_seconds: 2.0
      non_retryable_errors:
        - AuthenticationError
```

### RetryConfig fields

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `max_attempts` | `int` | `3` | `1 -- 20` | Total attempts (1 = no retry) |
| `backoff` | `"fixed" \| "exponential"` | `"fixed"` | --- | Backoff strategy between attempts |
| `backoff_base_seconds` | `float` | `1.0` | `0.1 -- 60.0` | Base delay between retries |
| `non_retryable_errors` | `list[str]?` | `None` | --- | Exception type names that should not be retried |

### Backoff strategies

**Fixed backoff** (`backoff: "fixed"`): Waits `backoff_base_seconds` between every retry attempt.

```
Attempt 1 → fail → wait 1.0s → Attempt 2 → fail → wait 1.0s → Attempt 3
```

**Exponential backoff** (`backoff: "exponential"`): Doubles the delay each attempt using `backoff_base_seconds * 2^(attempt-1)`.

```
Attempt 1 → fail → wait 2.0s → Attempt 2 → fail → wait 4.0s → Attempt 3
```

### Retry behavior

- Each retry starts from the **original pre-retry state**. Failed-attempt messages are never carried over to the next attempt.
- On success after retries, the block result includes retry metadata in `shared_memory` under `__retry__{block_id}`:

```json
{
  "attempt": 2,
  "max_attempts": 3,
  "last_error": "Connection timeout",
  "last_error_type": "TimeoutError",
  "total_retries": 1
}
```

- If an error's type name matches an entry in `non_retryable_errors`, the error is raised immediately without further retry attempts.
- `KeyboardInterrupt` and `SystemExit` are never retried.

## Error propagation lifecycle

Here is how errors flow through the execution engine:

1. **Block raises an exception** during `execute_block()`.

2. **Retry check:** If `retry_config` is set and `max_attempts > 1`, the block is retried according to the backoff strategy. Non-retryable errors skip this step.

3. **Error route check:** If `error_route` is set on the block, the exception is caught, a `BlockResult` with error metadata is written, and execution redirects to the error route target.

4. **Workflow-level propagation:** If no error_route is set, the exception propagates up to the workflow runner. If the workflow is a child (running inside a `workflow` block), the parent's `on_error` determines what happens next.

5. **Terminal state:** If the exception reaches the top-level workflow, the run is marked as `failed` with the error message and traceback stored on the `Run` record.

### Combining error_route with retry_config

You can use both on the same block. Retries are attempted first. If all retry attempts are exhausted and the block still fails, the error_route takes over:

```yaml title="Retry then redirect"
blocks:
  api_call:
    type: linear
    soul_ref: analyst
    retry_config:
      max_attempts: 3
      backoff: exponential
      backoff_base_seconds: 1.0
    error_route: handle_api_failure
  handle_api_failure:
    type: linear
    soul_ref: error_handler
```

## Block timeout

Every block has a `timeout_seconds` field (default: `300`, range: `1 -- 3600`) separate from the budget `limits.max_duration_seconds`. If the block execution exceeds this timeout, a `BudgetKilledException` is raised with `limit_kind="timeout"`. This exception can be caught by `error_route` or `retry_config` like any other error.

See [Budget & Limits](/docs/execution/budget-and-limits) for the full budget enforcement model.

<!-- Linear: RUN-554, RUN-590, RUN-708 — last verified against codebase 2026-04-07 -->
