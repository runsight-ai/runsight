---
title: Running Workflows
description: Production runs vs simulation runs — how Runsight executes workflows and tracks run history.
---

Runsight has two execution modes: **production runs** on the main branch and **simulation runs** on disposable branches. Every run is persisted as a database record with per-block node tracking, parent-child linkage for sub-workflows, and a commit SHA tying the run back to the exact YAML that executed.

## Run lifecycle

A run moves through a fixed state machine:

| State | Meaning |
|-------|---------|
| `pending` | Created in the database, waiting for a concurrency slot |
| `running` | Actively executing blocks |
| `completed` | All blocks finished successfully |
| `failed` | A block raised an unhandled error or a budget limit was exceeded |
| `cancelled` | Stopped by user action or server shutdown |

Terminal states (`completed`, `failed`, `cancelled`) are final --- no further transitions are allowed. The valid transitions are:

- `pending` &rarr; `running`, `cancelled`, `failed`
- `running` &rarr; `completed`, `failed`, `cancelled`

## Production runs

A production run executes the workflow YAML as committed on the **main branch**. When you click **Run** in the GUI with no unsaved changes, or call the API with `branch: "main"`:

1. The API reads the workflow YAML from `git show main:custom/workflows/{id}.yaml`.
2. A `Run` record is created with `status: pending` and `branch: "main"`.
3. The execution service acquires a concurrency slot (default: 5 concurrent runs), then transitions the run to `running`.
4. The engine parses the YAML, builds a `Workflow` graph, and calls `Workflow.run()`.
5. Each block executes sequentially through the transition graph. A `RunNode` record is created per block.
6. On completion, the observer writes `status: completed` with final cost and token totals.

```bash title="API — create a production run"
curl -X POST http://localhost:8321/api/runs \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "research-pipeline",
    "task_data": { "instruction": "Research quantum computing trends" },
    "branch": "main"
  }'
```

## Simulation runs

When the workflow has **unsaved changes** (the canvas shows an uncommitted badge), clicking **Run** creates a simulation run:

1. The GUI calls `POST /api/git/sim-branch` with the current YAML draft.
2. A simulation branch is created with the naming convention `sim/{workflow-slug}/{YYYYMMDD}/{short-id}` (e.g., `sim/research-pipeline/20260407/a3f1b`).
3. The run is created with `branch: "sim/research-pipeline/20260407/a3f1b"` and `source: "manual"`.
4. Execution proceeds identically to a production run, but reads the YAML from the sim branch snapshot.

Simulation branches are disposable --- they capture the exact state of the workflow at the time of the run, including any unsaved edits. See [Git Integration](/docs/execution/git-integration) for details on how sim branches work.

## The Run record

Each run is stored as a `Run` row in the SQLite database with these fields:

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Primary key (UUID) |
| `workflow_id` | `str` | Which workflow was executed |
| `workflow_name` | `str` | Human-readable workflow name |
| `status` | `RunStatus` | Current state (`pending` / `running` / `completed` / `failed` / `cancelled`) |
| `branch` | `str` | Git branch this run executed against (default: `"main"`) |
| `source` | `str` | How the run was triggered (default: `"manual"`) |
| `commit_sha` | `str?` | Git commit SHA of the YAML that executed |
| `total_cost_usd` | `float` | Accumulated LLM cost |
| `total_tokens` | `int` | Accumulated token count |
| `error` | `str?` | Error message if the run failed |
| `fail_reason` | `str?` | Structured failure category (e.g., `"budget_exceeded"`) |
| `parent_run_id` | `str?` | Parent run ID for sub-workflow runs |
| `root_run_id` | `str?` | Top-level ancestor run ID |
| `depth` | `int` | Nesting depth (0 for top-level runs) |

## RunNode — per-block tracking

Each block execution within a run creates a `RunNode` record:

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Composite key: `{run_id}:{node_id}` |
| `node_id` | `str` | Block ID from the workflow YAML |
| `block_type` | `str` | Block type (`linear`, `gate`, `code`, `loop`, `workflow`) |
| `status` | `NodeStatus` | `pending` / `running` / `completed` / `failed` |
| `cost_usd` | `float` | Cost for this block's LLM calls |
| `tokens` | `dict` | Token breakdown: `{"prompt": N, "completion": N, "total": N}` |
| `output` | `str?` | Block output text |
| `eval_score` | `float?` | Assertion evaluation score |
| `eval_passed` | `bool?` | Whether all assertions passed |
| `child_run_id` | `str?` | For workflow blocks: the child run's ID |
| `exit_handle` | `str?` | Which exit port this block took |

## Sub-workflow runs

When a workflow contains a `workflow` block, the child workflow executes as a nested run. The parent `RunNode` records the `child_run_id`, and the child `Run` stores `parent_run_id`, `root_run_id`, and `depth`. This creates a tree of runs that you can query via the API:

```bash title="API — list child runs"
curl http://localhost:8321/api/runs/{parent_run_id}/children
```

The child run response includes `parent_run_id`, `root_run_id`, and `depth` fields so you can reconstruct the full execution tree.

## Ghost run recovery

If the server restarts while runs are in `running` status, those runs become "ghosts" --- they will never complete because the asyncio task is gone. On startup, the execution service calls `fail_ghost_runs()` to mark all `running` runs as `failed` with the error message `"Ghost run: server restarted while running"`.

## Triggering runs

| Method | How |
|--------|-----|
| **GUI** | Click the **Run** button on the canvas topbar. Enter an instruction in the run dialog. |
| **API** | `POST /api/runs` with `workflow_id`, `task_data` (must include `instruction`), optional `branch` and `source`. |

:::note
There is no cron or webhook trigger yet. All runs are currently triggered manually through the GUI or API.
:::

<!-- Linear: RUN-554, RUN-590, RUN-607, RUN-717 — last verified against codebase 2026-04-07 -->
