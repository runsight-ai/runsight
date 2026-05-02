# Full Test Cleanup Audit

This is the current cleanup map for the test surface on branch
`codex/run-984-985-test-isolation`. It answers which test files are aligned,
which need cleanup, and what kind of cleanup each file needs before we continue
refactoring.

## Coverage

- Current test files inventoried: 566
- Reviewed rows in `full-test-cleanup-map.tsv`: 566
- Tier 1 Bronze delete completed: 51 files removed
- Tier 1 RGB gate: Red matrix approved, Blue approved, Yellow approved
- Tier 2 Silver merge/delete completed: 130 assigned duplicate files removed,
  3 consolidated tools governance owners added, and 5 GUI settings files
  escalated because no safe rendered settings owner exists yet
- Tier 2 RGB gate: Red matrix approved, Blue approved, Yellow approved
- Tier 3 Silver move-to-tooling completed: 22 app/package governance suites
  moved or deleted, 3 consolidated tools governance owners added, and 1 stale
  tools guard removed after its target suite was retired
- Tier 3 RGB gate: Blue approved, Yellow approved
- Full test suites run: none

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
| KEEP | 366 |
| SHRINK_TO_SMOKE | 70 |
| SPLIT | 75 |
| EXTERNALIZE_FIXTURES | 44 |
| REVIEW_DEEP | 11 |

### By Alignment Status

| Status | Count |
|---|---:|
| aligned | 366 |
| cleanup_needed | 148 |
| shrink_candidate | 50 |
| move_candidate | 1 |
| red_unfinished | 1 |

### By Workspace And Action

| Workspace | KEEP | DELETE | MERGE_THEN_DELETE | SHRINK_TO_SMOKE | SPLIT | EXTERNALIZE_FIXTURES | MOVE_TO_TOOLING | REVIEW_DEEP | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| api | 117 | 0 | 0 | 12 | 16 | 30 | 0 | 3 | 178 |
| core | 150 | 0 | 0 | 24 | 49 | 2 | 0 | 2 | 227 |
| e2e | 11 | 0 | 0 | 5 | 1 | 0 | 0 | 1 | 18 |
| gui | 66 | 0 | 0 | 8 | 8 | 12 | 0 | 5 | 99 |
| shared | 5 | 0 | 0 | 5 | 0 | 0 | 0 | 0 | 10 |
| tools | 8 | 0 | 0 | 4 | 0 | 0 | 0 | 0 | 12 |
| ui | 9 | 0 | 0 | 12 | 1 | 0 | 0 | 0 | 22 |

## Interpretation

The epic is not done. The audit says 200 of 566 current test files still need a
cleanup action before the test surface matches the target convention.

The biggest cleanup opportunities are:

- Split god-object suites with mixed concerns: 75 suites.
- Shrink browser-heavy, route-mocked, or matrix-heavy suites to smoke coverage:
  70 suites.
- Externalize large inline fixtures, mostly API and GUI: 44 suites.
- Deep-review blockers and escalations: 11 suites.

Tier 1 removed the original 51 direct delete candidates. Tier 2 removed the
merge/delete queue. It left five GUI settings source-scan files intentionally
escalated until a proper rendered settings owner exists. Tier 3 removed the
move-to-tooling queue from app/package workspaces and consolidated durable
repo/source governance under `tools/tests`.

## High-Risk Items

- `packages/core/tests/test_exit_port_suite_ownership_governance.py` is marked
  `red_unfinished`; static inspection found the expected exit-port helper/owner
  suites missing, so deletion is blocked until the intended owner suites exist.
- `packages/core/tests/conftest.py` is `REVIEW_DEEP`; global autouse isolation
  can hide subprocess/runtime regressions and needs careful review before
  changing.
- Route-mocked browser contracts such as context audit and parser warnings need
  owner decisions: GUI browser-contract tests versus true E2E smoke.
- The five escalated GUI settings suites need a rendered settings owner before
  they can be safely merged and deleted.

## Next Execution Order

1. Shrink `SHRINK_TO_SMOKE` suites so browser/integration tests only cover the
   user-visible wiring that lower-level tests cannot cover.
2. Split `SPLIT` god suites by behavior owner.
3. Externalize fixture bulk into package-local builders/fixtures.
4. Resolve `REVIEW_DEEP` blockers, including the GUI settings escalation.
5. Run targeted RGB TDD per cleanup batch, never full pytest/vitest/playwright.

Use `tools/test-audit/full-test-cleanup-map.tsv` as the source of truth for the
ticket breakdown and review checklist.
