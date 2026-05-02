# Full Test Cleanup Audit

This directory is a planning artifact for the test cleanup/refactor effort.
It is intentionally separate from behavior tests.

Goal: map every current test/spec file and decide whether it should be kept,
deleted, merged, shrunk, moved, split, or have fixtures externalized.

## Files

- `current-test-inventory.tsv`: generated inventory of every current test/spec file.
- `shards/*.tsv`: per-workspace review maps written by audit agents.
- `full-test-cleanup-map.tsv`: final merged map, one row per current test/spec file.

## Review Columns

Each shard uses this TSV schema:

```text
path	loc	current_behavior	alignment_status	primary_action	reason	mirror_or_duplicate_of	fixture_plan	verification_target	confidence
```

Allowed `alignment_status` values:

- `aligned`
- `cleanup_needed`
- `delete_candidate`
- `merge_candidate`
- `shrink_candidate`
- `move_candidate`
- `red_unfinished`

Allowed `primary_action` values:

- `KEEP`
- `DELETE`
- `MERGE_THEN_DELETE`
- `SHRINK_TO_SMOKE`
- `EXTERNALIZE_FIXTURES`
- `SPLIT`
- `MOVE_TO_TOOLING`
- `REVIEW_DEEP`

## Review Rules

- Prefer deletion of duplicated or temporary migration coverage.
- E2E should be smoke-level unless the behavior cannot be tested lower.
- Fixture data belongs to the owning workspace, not repo-root runtime state.
- Governance tests need a durable owner and exit criteria; temporary guards should be deleted after behavior owners exist.
- A split is only useful when the old owner is deleted or meaningfully reduced.
