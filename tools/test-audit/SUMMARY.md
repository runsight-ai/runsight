# Full Test Cleanup Audit

This is a static review map for the current test surface on branch
`codex/run-984-985-test-isolation`. It does not claim tests pass; it answers
which test files are aligned, which need cleanup, and what kind of cleanup each
file needs before we continue refactoring.

## Coverage

- Current test files inventoried: 765
- Reviewed rows in `full-test-cleanup-map.tsv`: 765
- Missing files after merge validation: 0
- Duplicate reviewed files after merge validation: 0
- Test commands run during audit: none

The merged file is `tools/test-audit/full-test-cleanup-map.tsv`.

## Review Dimensions

Each test file was reviewed for:

- current behavior under test
- whether the suite is behavior/feature/flow named rather than ticket or
  temporary migration named
- whether it is a mirror of a source file without clear behavior ownership
- duplicated or similar coverage that can be unified into a stronger owner
- oversized "god suite" behavior, mixed concerns, or matrix bloat
- inline fixture bulk that should move to package-local builders or fixture
  files
- ownership violations, especially cross-workspace fixtures
- repo-root runtime state risks such as `.runsight/`, `runsight.db`, `custom/`,
  user config, templates, or secrets
- live third-party/network risk
- governance/source-scan suites that belong in tooling, should shrink, or
  should expire after cleanup
- deterministic targeted verification command for later RGB execution

## Summary Counts

### By Primary Action

| Action | Count |
|---|---:|
| KEEP | 360 |
| DELETE | 51 |
| MERGE_THEN_DELETE | 135 |
| SHRINK_TO_SMOKE | 72 |
| SPLIT | 75 |
| EXTERNALIZE_FIXTURES | 44 |
| MOVE_TO_TOOLING | 22 |
| REVIEW_DEEP | 6 |

### By Alignment Status

| Status | Count |
|---|---:|
| aligned | 360 |
| cleanup_needed | 160 |
| delete_candidate | 54 |
| merge_candidate | 119 |
| shrink_candidate | 50 |
| move_candidate | 21 |
| red_unfinished | 1 |

### By Workspace And Action

| Workspace | KEEP | DELETE | MERGE_THEN_DELETE | SHRINK_TO_SMOKE | SPLIT | EXTERNALIZE_FIXTURES | MOVE_TO_TOOLING | REVIEW_DEEP | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| api | 117 | 13 | 11 | 12 | 16 | 30 | 6 | 3 | 208 |
| core | 150 | 20 | 48 | 24 | 49 | 2 | 7 | 2 | 302 |
| e2e | 11 | 2 | 9 | 5 | 1 | 0 | 0 | 1 | 29 |
| gui | 66 | 14 | 26 | 8 | 8 | 12 | 9 | 0 | 143 |
| shared | 5 | 1 | 4 | 5 | 0 | 0 | 0 | 0 | 15 |
| tools | 2 | 0 | 29 | 6 | 0 | 0 | 0 | 0 | 37 |
| ui | 9 | 1 | 8 | 12 | 1 | 0 | 0 | 0 | 31 |

## Interpretation

The epic is not done. The audit says 405 of 765 current test files still need a
cleanup action before the test surface matches the target convention.

The biggest cleanup opportunities are:

- Delete temporary migration/source-scan guards: 51 direct deletes.
- Merge duplicated small suites into stronger behavior owners: 135 merge/delete
  candidates.
- Shrink browser-heavy, route-mocked, or matrix-heavy suites to smoke coverage:
  72 suites.
- Split god-object suites with mixed concerns: 75 suites.
- Externalize large inline fixtures, mostly API and GUI: 44 suites.
- Move repo/source governance out of app/package tests into tooling: 22 suites.

## High-Risk Items

- `packages/core/tests/test_exit_port_suite_ownership_governance.py` is marked
  `red_unfinished`; static inspection found the expected exit-port helper/owner
  suites missing, so deletion is blocked until the intended owner suites exist.
- `packages/core/tests/conftest.py` is `REVIEW_DEEP`; global autouse isolation
  can hide subprocess/runtime regressions and needs careful review before
  changing.
- Route-mocked browser contracts such as context audit and parser warnings need
  owner decisions: GUI browser-contract tests versus true E2E smoke.
- Tooling/governance suites are the largest low-signal cluster. Many are
  temporary one-off guards created during this cleanup and should collapse into
  a small number of durable policy checks or be deleted.

## Next Execution Order

1. Delete direct `DELETE` candidates with high confidence.
2. Collapse `MERGE_THEN_DELETE` suites into the named owner suites and delete
   the redundant files.
3. Move `MOVE_TO_TOOLING` governance out of app/package test workspaces or
   delete it if it is temporary migration residue.
4. Shrink `SHRINK_TO_SMOKE` suites so browser/integration tests only cover the
   user-visible wiring that lower-level tests cannot cover.
5. Split `SPLIT` god suites by behavior owner.
6. Externalize fixture bulk into package-local builders/fixtures.
7. Run targeted RGB TDD per cleanup batch, never full pytest/vitest/playwright.

Use `tools/test-audit/full-test-cleanup-map.tsv` as the source of truth for the
ticket breakdown and review checklist.
