---
title: Run Detail View
description: Inspecting completed and running workflows — per-block status, logs, regressions, historical YAML, cost and token metrics, and fork recovery.
---

The Run Detail view is a read-only inspection surface for individual workflow runs. It shows per-block execution results on a canvas, structured logs, regression analysis, and the exact YAML that was executed. You reach it by clicking a run row in the Runs page or the Runs tab in the bottom panel.

## Layout

The Run Detail view is a full-page layout with four regions:

1. **Header** — workflow name, run status badge, aggregate metrics, and action buttons
2. **Center** — either the execution canvas (block nodes with status coloring) or the historical YAML editor, toggled via tabs
3. **Inspector** — a slide-in right panel showing per-block details when you click a node
4. **Bottom panel** — collapsible panel with Logs, Runs, and Regressions tabs

## Header

The header displays:

| Element | Description |
|---------|-------------|
| **Back link** | Navigates to the Runs list |
| **Workflow name** | The name of the workflow that produced this run |
| **Status badge** | Colored badge: green for completed, red for failed/error, yellow for running/pending |
| **"Read-only review" badge** | Indicates this is a non-editable inspection view |
| **Duration** | Total wall-clock time for the run |
| **Token count** | Total tokens consumed across all blocks (formatted as "1.2k tok" for large numbers) |
| **Cost** | Total cost in USD |

### Action buttons

| Button | When visible | Behavior |
|--------|-------------|----------|
| **Cancel** | Run is active (running or pending) | Sends a cancel request to abort the run |
| **Open Workflow** | Run is not active | Navigates to the workflow's edit surface |
| **Fork** | Run is not active and has a commit snapshot | Creates a new workflow from the run's historical YAML |

:::note
The Fork button is disabled in two cases: when the run is still active (wait for it to finish) and when no commit snapshot is available (the run's YAML was never committed). A tooltip explains the reason when you hover over the disabled button.
:::

## Execution canvas

The default center view is a ReactFlow canvas showing each block as a node. Nodes are **not draggable and not connectable** — this is a read-only visualization of the execution graph.

Each node displays:

- **Block name** — the block ID from the workflow
- **Status badge** — idle, pending, running, completed, or failed
- **Cost** — actual execution cost in USD (e.g., "$0.003")
- **Duration and tokens** — shown in a footer row when available (e.g., "1.2s, 450 tokens")
- **Error message** — shown in a red banner at the bottom of failed nodes

Node borders change color based on status:
- **Green** (`--success-9`) — completed
- **Red** (`--danger-9`) with a glow shadow — failed
- **Muted** with reduced opacity — pending
- **Default** — idle

The MiniMap in the corner color-codes nodes: green for completed, red for failed, muted for pending, blue for running.

### Error states

When the run graph cannot be loaded (API error), a retry card is shown instead of the canvas. When the run failed before any blocks executed (e.g., YAML validation error), a card displays the pre-execution error message.

## Block inspector

Click any node on the canvas to open the right inspector panel. It slides in from the right with two tabs:

### Execution tab

Shows the block's runtime results:

- **Status banner** — colored banner (green/red/neutral) with the status label and duration
- **Cost** — the block's execution cost in USD
- **Token usage** — prompt tokens, completion tokens, and total, each with a progress bar showing the proportion of total
- **Error** — if the block failed, the error message appears in a red box
- **Configuration** — soul reference and model used by this block

### Overview tab

Shows the block's identity:

- **Name** — the block ID
- **Status** — as a badge
- **Configuration** — soul reference and model

Close the inspector by clicking the X button or clicking on empty canvas space.

## Historical YAML snapshot

Switch to the YAML tab in the header to see the exact YAML that was executed for this run. This is retrieved from git using the run's `commit_sha`:

1. The Run Detail component reads `run.commit_sha` and `run.workflow_id`
2. It calls the git API to fetch the file at `custom/workflows/{workflow_id}.yaml` at that specific commit
3. The YAML is displayed in a read-only Monaco editor

This matters because the workflow may have been modified after the run completed. The historical snapshot shows you exactly what executed, not the current state of the file.

If the run has no commit SHA (e.g., it was a simulation run from uncommitted changes), the editor falls back to showing the current workflow YAML. If no YAML is available at all, a placeholder message is shown.

## Bottom panel

The bottom panel is expanded by default in the Run Detail view. It has three tabs:

### Logs tab

Displays structured log entries for the run. Each log line shows:

- **Timestamp** — when the event occurred
- **Level** — INFO, WARN, ERROR, or DEBUG, each with its own color styling
- **Node ID** — which block produced the log (when applicable)
- **Message** — the log content

A summary banner appears at the top when the run is complete:
- Green banner with checkmark: "Run completed in X.Xs"
- Red banner with X icon: "Run failed"

### Runs tab

Shows all runs for the same workflow in a table, sorted by most recent first. The current run is highlighted. Click a different run row to navigate to its detail view.

### Regressions tab

Compares this run against historical runs for the same workflow to detect quality or cost regressions. Each regression entry shows:

- **Node name** — which block regressed
- **Type** — the kind of regression (e.g., cost increase, score decrease)
- **Delta** — the magnitude of the change (e.g., "+15%" for cost, "-0.3" for score)

When regressions are detected, a `PriorityBanner` appears above the canvas with the count (e.g., "3 regressions found"), drawing attention before you even look at the tab.

If no regressions are detected, the tab shows "No regressions detected for this run."

## Fork recovery

The Fork button enables a recovery workflow for failed runs:

1. Click Fork on a completed or failed run
2. Runsight reads the YAML from the run's commit snapshot (the exact YAML that executed)
3. It creates a new workflow with `enabled: false` and a generated name based on the original workflow
4. You are navigated to the new workflow's edit surface
5. Fix the issue in the YAML, save, and run again

The fork is created as an uncommitted draft — it will not auto-execute. The `enabled: false` flag prevents accidental runs before you have reviewed and fixed the YAML.

:::caution
Fork requires a commit snapshot. If the run was triggered from uncommitted (dirty) YAML via a simulation branch, no snapshot is available and the Fork button is disabled.
:::

## Live updates for active runs

When viewing an active run (status: running or pending), the Run Detail polls for updates:

- The run metadata refreshes every 2 seconds while the run is active
- Node statuses update as blocks complete or fail
- Logs appear in real time
- Once the run reaches a terminal state (completed/failed), polling stops

<!-- Linear: RUN-649, RUN-749, RUN-746, Visual Workflow Builder project, Run Inspection & Fork Recovery epic — last verified against codebase 2026-04-07 -->
