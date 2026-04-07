---
title: Fork Recovery
description: Fork from a failed run to iterate on your workflow without losing the original run history.
---

Fork recovery lets you take a failed (or completed) run, read the exact YAML that executed, and create a new draft workflow from it. You iterate on the draft, fix the issue, and run again --- all without modifying the original workflow or losing the run history.

## When to fork

Fork is the primary recovery path when a run fails. Instead of editing the live workflow and hoping you remember what changed, forking gives you:

- The **exact YAML snapshot** from the failed run's `commit_sha`.
- A **new draft workflow** that is independent of the original.
- The original run history and the original workflow remain untouched.

## How to fork a run

### From the GUI

1. Open any completed or failed run from the **Runs** page.
2. The run detail view is read-only --- you cannot edit the YAML directly.
3. Click the **Fork** button in the topbar header.
4. Runsight creates a new draft workflow named `drft-{slug}-{short-id}` (e.g., `drft-research-pipeline-a3f1`).
5. The editor opens the new draft, ready for you to modify and re-run.

:::caution
The Fork button is **disabled** while a run is still active (`pending` or `running`). Wait for the run to finish before forking. It is also disabled if the run has no `commit_sha` (snapshot unavailable).
:::

### What happens under the hood

1. The frontend reads the workflow YAML at the run's commit SHA via `GET /api/git/file?ref={commit_sha}&path=custom/workflows/{workflow_id}.yaml`.
2. It parses the YAML and sets `enabled: false` so the draft does not appear as a live workflow.
3. It calls `POST /api/workflows` with `commit: false` to create the draft without auto-committing it. The draft appears as an uncommitted workflow.
4. The browser navigates to the new draft in edit mode.

No dedicated fork endpoint exists on the backend. The fork flow is composed entirely from existing primitives: git file read, workflow creation, and navigation.

### From the API

You can replicate the fork flow manually:

```bash title="Step 1: Read the YAML from the failed run's commit"
curl "http://localhost:8321/api/git/file?ref=abc1234&path=custom/workflows/research-pipeline.yaml"
```

```bash title="Step 2: Create a new draft workflow"
curl -X POST http://localhost:8321/api/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "name": "drft-research-pipeline-x9k2",
    "yaml": "... modified YAML ...",
    "commit": false
  }'
```

## Fork naming convention

Forked drafts follow the pattern:

```
drft-{slugified-workflow-name}-{4-char-random}
```

The slug is lowercase, non-alphanumeric characters replaced with hyphens, consecutive hyphens collapsed. The random suffix uses a 4-character alphanumeric string from `Math.random().toString(36)`.

Examples:
- `drft-research-pipeline-a3f1`
- `drft-customer-onboarding-zk92`

The `drft-` prefix signals that this workflow is a draft fork, not a production workflow.

## Priority banner

The canvas uses a **PriorityBanner** component to surface contextual alerts. The banner supports three condition types in priority order:

1. **explore** --- informational banner (info styling, dismissible with localStorage persistence).
2. **uncommitted** --- warning banner when the workflow has unsaved changes (warning styling, session-scoped dismiss).
3. **regressions** --- warning banner when eval regressions are detected (warning styling, session-scoped dismiss).

Only the highest-priority active banner is shown at a time. If you dismiss the top-priority banner, lower-priority banners do **not** cascade into view --- the dismiss is sticky for that session.

## Fork recovery workflow

The typical fork recovery loop:

1. A production run **fails** on the main branch.
2. You open the failed run from the Runs page.
3. You review the run detail --- block outputs, errors, eval results --- in read-only mode.
4. You click **Fork** to create a draft from the exact YAML that failed.
5. You edit the draft to fix the issue (adjust prompts, change transitions, modify limits).
6. You run the draft as a **simulation run** (since it has uncommitted changes).
7. If the simulation succeeds, you **save** the draft (commit to main) or copy the changes back to the original workflow.

This preserves the full audit trail: the original run, the fork point, and the iteration history are all distinct records.

<!-- Linear: RUN-554, RUN-557, RUN-564, RUN-590, RUN-595 — last verified against codebase 2026-04-07 -->
