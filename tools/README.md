# tools

Target home for developer tooling and repo automation.

Examples:

- code generation scripts
- migration helpers
- codemods
- repo maintenance utilities

Use `tools/` for supported repo-level tooling and automation entry points.

## Codebones Verification Flow

`codebones` is a developer tool, so the install and cache lifecycle belong here until we
have a dedicated tooling guide.

Install or upgrade it with `uv`:

```bash
uv tool install codebones
uv tool upgrade codebones
```

Verify the executable on your machine before you trust local index results:

```bash
uv tool list
codebones --version
```

Build or rebuild the local index from the repo root of the checkout, clone, or worktree
you are using:

```bash
codebones index .
```

That command is the lightweight regression check contributors should rerun after file
deletes, moves, or branch changes. After a reindex, removed files should disappear from
both targeted searches and `codebones search ""`.

The local cache artifact is `codebones.db`. It is scoped per checkout/worktree/clone, so
an old cache in one worktree does not refresh another one. If a cache upgrade fails or a
stale index survives unexpectedly, remove the local database and rebuild it:

```bash
rm -f codebones.db
codebones index .
```
