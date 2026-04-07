---
title: Regressions
description: How Runsight detects quality regressions by comparing runs -- assertion failures, cost spikes, and score drops.
---

Regressions are quality problems that appear when comparing consecutive runs of the same workflow. Runsight automatically detects three types of regression by comparing each production run against its predecessor.

## What counts as a regression

The `EvalService._detect_node_regressions` method compares two matching nodes (same `node_id` and `soul_version`) across consecutive production runs. It flags three conditions:

| Type | Condition | Delta payload |
|------|-----------|---------------|
| `assertion_regression` | `eval_passed` changed from `True` to `False` | `{eval_passed: false, baseline_eval_passed: true}` |
| `cost_spike` | Cost increased more than 20% vs previous run | `{cost_pct: <percentage>, baseline_cost: <previous cost>}` |
| `quality_drop` | `eval_score` dropped by more than 0.1 | `{score_delta: <negative number>}` |

Only **production runs** are compared -- runs on the `main` branch with a source of `manual`, `webhook`, or `schedule`. Simulation branches are excluded.

## How eval_score and eval_passed work

These fields live on the `RunNode` entity and are populated by the `EvalObserver` when a block with [assertions](/docs/evaluation/assertions) completes:

- **`eval_score`** (`Optional[float]`): The weighted average of all assertion scores for that node. A value of `1.0` means every assertion scored perfectly; `0.0` means all failed.
- **`eval_passed`** (`Optional[bool]`): `True` only if every individual assertion passed. A node can have a high score but still fail if one assertion did not pass.
- **`eval_results`** (`Optional[Dict]`): Detailed breakdown with per-assertion `type`, `passed`, `score`, and `reason`.

When a block has no assertions, all three fields are `None` and the node is excluded from regression detection.

## Run-to-run comparison

Regression detection works at the run level via the `EvalService`:

**For a single run** (`GET /api/runs/{run_id}/regressions`):

1. Find all production runs for the same workflow, ordered by `created_at`
2. Identify the previous production run before the target run
3. Match nodes between the two runs by `(node_id, soul_version)`
4. For each matching pair, check the three regression conditions
5. Return `{count: N, issues: [...]}` -- or `{count: 0, issues: []}` if this is the first run

**For a workflow** (`GET /api/workflows/{id}/regressions`):

1. Get all production runs for the workflow, ordered by `created_at`
2. For each consecutive pair, compare matching nodes
3. Each issue includes `run_id` and `run_number` to identify which run introduced it
4. Return the aggregate across all run pairs

The first production run of a workflow always has zero regressions since there is no baseline to compare against.

## Regression issue structure

Each regression issue in the response contains:

| Field | Type | Description |
|-------|------|-------------|
| `node_id` | `str` | The block that regressed |
| `node_name` | `str` | Display name of the node |
| `type` | `str` | One of `assertion_regression`, `cost_spike`, `quality_drop` |
| `delta` | `dict` | Type-specific comparison data (see table above) |
| `run_id` | `str` | (workflow endpoint only) Which run introduced this regression |
| `run_number` | `int` | (workflow endpoint only) Sequential run number |

## Pass rate tracking

Run-level pass rate is tracked via `eval_pass_pct` on the `RunResponse` schema. This field represents the percentage of eval-bearing nodes that passed in a run. The `RunResponse` also includes:

| Field | Type | Description |
|-------|------|-------------|
| `eval_pass_pct` | `Optional[float]` | Percentage of nodes with `eval_passed = True` |
| `eval_score_avg` | `Optional[float]` | Average `eval_score` across all eval-bearing nodes |
| `regression_count` | `Optional[int]` | Number of regression issues detected for this run |
| `regression_types` | `list[str]` | List of regression type strings found (e.g., `["assertion_regression", "cost_spike"]`) |

These fields appear in the runs list (`GET /api/runs`) and single run detail (`GET /api/runs/{id}`), enabling dashboards to show pass rate trends across runs.

## Regressions in the UI

The Run Detail view displays a priority banner when regressions are detected. The banner shows the regression count (e.g., "3 regressions found") and appears at the top of the run detail page.

The frontend fetches regression data via `useRunRegressions(runId)` and displays the count. The workflow-level regression query (`useWorkflowRegressions(workflowId)`) provides cross-run regression history.

The regression response schema on the frontend validates three regression types: `assertion_regression`, `cost_spike`, and `quality_drop`. Unknown types are rejected by the `WorkflowRegressionSchema` validator.

## Attention items

The `EvalService.get_attention_items` method scans production runs from the last 24 hours and surfaces regressions as attention items on the dashboard. It flags the same three conditions as the regression endpoints, plus a `new_baseline` info item for the first production run of a soul version. Items are sorted by severity (warnings before info) and recency.

<!-- Linear: RUN-555, RUN-558 -- last verified against codebase 2026-04-07 -->
