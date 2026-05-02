# Full Test Cleanup Audit

This is the current cleanup map for the test surface. It answers which test
files are aligned, which need cleanup, and what kind of cleanup each file needs
before we continue refactoring.

## Coverage

- Current test files inventoried: 738
- Reviewed rows in `full-test-cleanup-map.tsv`: 738
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
- Tier 7 pre-flight completed: the 11 remaining deep-review files are grouped
  into GUI settings, E2E context-audit, API governance, core subprocess
  isolation, and core exit-port batches in `tier-7-preflight.md`
- Tier 7 deep review completed: the final 11 cleanup rows were resolved into
  behavior owners, explicit subprocess-boundary markers, or deletions of stale
  source-scan/governance/fake-E2E suites
- Tier 7 RGB gate: Blue approved, Yellow approved after the subprocess marker
  follow-up
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
| KEEP | 738 |

### By Alignment Status

| Status | Count |
|---|---:|
| aligned | 738 |

### By Workspace And Action

| Workspace | KEEP | DELETE | MERGE_THEN_DELETE | SHRINK_TO_SMOKE | SPLIT | EXTERNALIZE_FIXTURES | MOVE_TO_TOOLING | REVIEW_DEEP | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| api | 215 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 215 |
| core | 349 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 349 |
| e2e | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 20 |
| gui | 109 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 109 |
| shared | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 10 |
| tools | 12 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 12 |
| ui | 23 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 23 |

## Interpretation

The cleanup epic is complete according to the audit map: all 738 current test
files are aligned and every row is marked `KEEP`.

The remaining cleanup queue is empty: 0 `REVIEW_DEEP`, 0 `SPLIT`, 0
`EXTERNALIZE_FIXTURES`, 0 `MOVE_TO_TOOLING`, and 0 delete/merge candidates.

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
package-local helpers while preserving behavior assertions in test files. Tier
7 removed the final deep-review queue by replacing GUI settings source scans
with rendered behavior owners, deleting the fake context-audit E2E owner,
shrinking API governance/source checks into behavior owners, making core real
subprocess coverage explicit through markers, and deleting the stale exit-port
governance suite.

## High-Risk Items

No high-risk cleanup rows remain in `full-test-cleanup-map.tsv`.

Residual risk: full pytest, Vitest, and Playwright suites were intentionally
not run because the repo forbids full-suite execution in agent sessions. Tier
validation used targeted owner commands plus Blue/Yellow review.

## Next Execution Order

1. Keep `full-test-cleanup-map.tsv` and `current-test-inventory.tsv` current
   when test files are added, renamed, or deleted.
2. Enforce the AGENTS.md naming, ownership, fixture, and isolation rules in RGB
   prompts so new tests do not reopen the cleanup queue.

Use `tools/test-audit/full-test-cleanup-map.tsv` as the source of truth for the
ticket breakdown and review checklist.
