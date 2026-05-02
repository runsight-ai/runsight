# Full Test Cleanup Audit

This is the current cleanup map for the test surface. It answers which test
files are aligned, which need cleanup, and what kind of cleanup each file needs
before we continue refactoring.

## Coverage

- Current test files inventoried: 739
- Reviewed rows in `full-test-cleanup-map.tsv`: 739
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
- Tier 4 Gold shrink-to-smoke completed: 70 broad browser/integration/source
  contract suites shrunk to representative smoke coverage
- Tier 4 RGB gate: Blue approved, Yellow approved
- Tier 5 Gold split completed: 75 broad SPLIT candidates removed, 248 focused
  behavior-owner suites added, and duplicated YAML/schema/source/string checks
  collapsed into existing owners where possible
- Tier 5 RGB gate: Blue approved, Yellow approved
- Tier 6 pre-flight completed: fixture-externalization candidates classified
  into API, GUI, and Core batches in `tier-6-preflight.md`
- Tier 6 fixture externalization completed: 44 suites moved repeated fixture
  bulk into owning-workspace helpers/builders while keeping assertions in the
  behavior suites
- Tier 6 RGB gate: Blue approved, Yellow approved after the
  snapshot-resolution fixture follow-up
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
| KEEP | 728 |
| REVIEW_DEEP | 11 |

### By Alignment Status

| Status | Count |
|---|---:|
| aligned | 728 |
| cleanup_needed | 9 |
| move_candidate | 1 |
| red_unfinished | 1 |

### By Workspace And Action

| Workspace | KEEP | DELETE | MERGE_THEN_DELETE | SHRINK_TO_SMOKE | SPLIT | EXTERNALIZE_FIXTURES | MOVE_TO_TOOLING | REVIEW_DEEP | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| api | 210 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 213 |
| core | 348 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 350 |
| e2e | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 21 |
| gui | 105 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 110 |
| shared | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 10 |
| tools | 12 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 12 |
| ui | 23 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 23 |

## Interpretation

The epic is not done. The audit says 11 of 739 current test files still need a
cleanup action before the test surface matches the target convention.

The remaining cleanup work is the deep-review blocker/escalation queue: 11
suites.

Tier 1 removed the original 51 direct delete candidates. Tier 2 removed the
merge/delete queue. It left five GUI settings source-scan files intentionally
escalated until a proper rendered settings owner exists. Tier 3 removed the
move-to-tooling queue from app/package workspaces and consolidated durable
repo/source governance under `tools/tests`. Tier 4 removed the shrink queue by
reducing broad browser/integration/source-contract suites to representative
smoke coverage. Tier 5 removed the split queue by replacing broad mixed suites
with behavior-named owner suites, deleting duplicated low-signal assertions, and
moving shared setup into owning-workspace helpers where useful. Tier 6 removed
the fixture-externalization queue by moving repeated YAML, JSON, static render
harnesses, mock services, provider payloads, and temp repo builders into
package-local helpers while preserving behavior assertions in test files.

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

1. Resolve `REVIEW_DEEP` blockers, including the GUI settings escalation.
2. Run targeted RGB TDD per cleanup batch, never full pytest/vitest/playwright.

Use `tools/test-audit/full-test-cleanup-map.tsv` as the source of truth for the
ticket breakdown and review checklist.
