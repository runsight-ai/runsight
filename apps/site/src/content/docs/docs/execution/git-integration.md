---
title: Git Integration
description: Save = commit to main. Dirty runs create simulation branches. Every run snapshots the YAML that executed.
---

Runsight is git-native by design. Git is not optional --- it is required for the workflow persistence model to function. Every save is a commit, every run records a commit SHA, and simulation branches capture dirty state for reproducible execution.

## Git auto-initialization

When Runsight starts and no git repository exists at the project root, it automatically initializes one:

1. Runs `git init` in the project base path.
2. Configures a local git identity (`Runsight <runsight@localhost>`).
3. Stages all project files and creates an initial commit: `"Initial Runsight project"`.

This happens inside `scaffold_project()` during project detection. The result is that every Runsight project is always inside a git repository from the first launch.

## Save = commit to main

When you click **Save** in the canvas topbar, the workflow YAML is committed directly to the `main` branch. There is no separate "save" concept --- saving and committing are the same operation.

The commit flow:

1. The GUI calls `POST /api/git/commit` with the changed files and a commit message.
2. The git service stages the specified files (or all files if none are specified).
3. A commit is created on the current branch.
4. The response returns the new commit hash.

```bash title="API — commit changes"
curl -X POST http://localhost:8321/api/git/commit \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Update research-pipeline workflow",
    "files": ["custom/workflows/research-pipeline.yaml"]
  }'
```

:::note
Files matched by `.gitignore` patterns are silently skipped during staging. The commit proceeds with only the versionable files.
:::

## Simulation branches

When you run a workflow with unsaved changes, a simulation branch captures the exact state:

**Branch naming convention:**
```
sim/{workflow-slug}/{YYYYMMDD}/{5-char-hex}
```

Example: `sim/research-pipeline/20260407/a3f1b`

**How it works:**

1. The GUI sends `POST /api/git/sim-branch` with the workflow ID and current YAML content.
2. The git service creates a temporary index starting from `HEAD`.
3. It stages the entire worktree into that index (so parent/child workflow files are included).
4. It force-overrides the target workflow file with the in-memory YAML draft.
5. A commit is created from this tree, and a branch is pointed at it.
6. The response returns the branch name and commit SHA.

```bash title="API — create a simulation branch"
curl -X POST http://localhost:8321/api/git/sim-branch \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "research-pipeline",
    "yaml_content": "version: \"1.0\"\nworkflow:\n  name: research-pipeline\n  entry: step_one\n..."
  }'
```

The simulation branch is a real git branch pointing to a real commit. It includes the full worktree snapshot, not just the modified workflow file. This matters for workflows that reference other workflows via `workflow_ref` --- those child workflow files are resolved from the same branch.

## Run-to-commit tracking

Every run records two git coordinates:

| Field | Source | Purpose |
|-------|--------|---------|
| `branch` | Request parameter (default: `"main"`) | Which branch the YAML was read from |
| `commit_sha` | `git log -1 --format=%H -- {path}` on the branch | Exact commit that last touched this workflow file |

When git is configured, the execution service always reads the workflow YAML from the requested branch using `git show {branch}:{path}`, not from the filesystem. This guarantees the run executes the committed version, not whatever is in the working tree.

## Historical YAML snapshots

The run detail view shows the YAML **as it was when the run executed**, not the current version. This uses the `commit_sha` stored on the run record:

```bash title="API — read historical YAML"
curl "http://localhost:8321/api/git/file?ref=abc1234&path=custom/workflows/research-pipeline.yaml"
```

This powers the fork recovery flow --- when you fork a failed run, the fork reads the YAML from the run's `commit_sha` to create a new draft based on the exact version that failed. See [Fork Recovery](/docs/execution/fork-recovery) for details.

## Git endpoints

The API exposes these git operations:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/git/status` | Current branch, uncommitted files, is_clean flag |
| `POST` | `/api/git/commit` | Stage files and commit with a message |
| `GET` | `/api/git/diff` | Diff of working tree against HEAD |
| `GET` | `/api/git/log` | Last 50 commits (hash, message, date, author) |
| `GET` | `/api/git/file` | Read a file at a specific ref (branch or SHA) |
| `POST` | `/api/git/sim-branch` | Create a simulation branch from a YAML draft |

All endpoints validate paths against the project root to prevent directory traversal. Absolute paths outside the project root, paths starting with `-`, and symlinks escaping the project boundary are rejected.

## The unsaved indicator

The canvas topbar shows a small dot and a **Save** button when the workflow has unsaved changes. This indicator is driven by local `isDirty` state in the editor --- it tracks whether the in-memory YAML differs from the last saved version, not the git status endpoint. Clicking **Save** opens a `CommitDialog` which commits the changes via `POST /api/workflows/{id}/commits`, clears the dirty state, and the next run will execute from `main` instead of creating a sim branch.


<!-- Linear: RUN-557, RUN-747, RUN-749 — last verified against codebase 2026-04-07 -->
