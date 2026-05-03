# Tier 7 Deep Review Pre-Flight

Date: 2026-05-02

## Scope

Tier 7 is the final deep-review cleanup tier. It handles the 11 remaining
`REVIEW_DEEP` rows in `tools/test-audit/full-test-cleanup-map.tsv` after Tier 6
removed the fixture-externalization queue.

Pre-flight audit state:

| Metric | Count |
|---|---:|
| Mapped test files | 739 |
| Aligned `KEEP` files | 728 |
| Tier 7 `REVIEW_DEEP` files | 11 |
| Remaining `EXTERNALIZE_FIXTURES` files | 0 |
| Remaining `SPLIT` files | 0 |

Workspace breakdown for Tier 7:

| Workspace | Files |
|---|---:|
| API | 3 |
| GUI | 5 |
| Core | 2 |
| E2E | 1 |

## Tier 7 Goal

Resolve every remaining deep-review row with an explicit owner decision:

- keep as aligned behavior coverage
- delete as stale or duplicated coverage
- merge into an existing behavior owner and delete the source/mirror suite
- move route-mocked browser-contract coverage out of E2E ownership
- replace unfinished governance guards with durable owner suites and helpers

Expected audit outcome after Tier 7:

| Action | Expected Count |
|---|---:|
| KEEP | 739, adjusted for any deleted/replacement files |
| REVIEW_DEEP | 0 |
| EXTERNALIZE_FIXTURES | 0 |
| SPLIT | 0 |

The exact final `KEEP` count may change if source-scan or governance suites are
deleted and replaced with fewer behavior-owner suites. The invariant is no
remaining cleanup action rows.

## Completion Result

Tier 7 is complete as of 2026-05-02.

Final audit state:

| Metric | Count |
|---|---:|
| Mapped test files | 738 |
| Aligned `KEEP` files | 738 |
| Remaining `REVIEW_DEEP` files | 0 |
| Remaining `EXTERNALIZE_FIXTURES` files | 0 |
| Remaining `SPLIT` files | 0 |

Resolved owner decisions:

- GUI settings source-regex suites were deleted and replaced by rendered
  Settings page, provider-management, fallback, and setup accessibility owners.
- The route-mocked context-audit E2E spec and helper were deleted; missing
  denied/error/long-reference assertions moved to GUI context-audit owners.
- API source/governance-heavy suites were shrunk into behavior owners for SSE
  event names, streaming/registry behavior, read-model factory wiring, and
  workflow YAML validation.
- Core subprocess isolation no longer uses filename-prefix exclusions. Tests
  that exercise the real subprocess boundary now opt out explicitly with
  `real_subprocess_isolation`; the 61 legacy real-isolation owner files are
  marked at module level.
- The stale 1,041-line exit-port governance suite was deleted after focused
  exit/loop/output-condition owner suites were targeted-verified.

RGB gate:

- Blue approved the updated Tier 7 diff after the subprocess marker follow-up.
- Yellow approved the intent alignment after the subprocess marker follow-up.
- Full pytest, Vitest, and Playwright suites were not run, per repo rule; only
  targeted verification commands were used.

## Definition Of Done

- No test file remains marked `REVIEW_DEEP`, `red_unfinished`, or
  `move_candidate` in the audit map.
- No GUI settings test remains a source-regex/readSource guard when the behavior
  can be rendered through React Testing Library.
- No route-mocked browser contract remains classified as true E2E unless it is
  shrunk to a live-route smoke. Route/API-mocked GUI contracts move to GUI
  ownership or delete if lower-level owners already cover the behavior.
- No 1k-line governance suite remains as a permanent substitute for behavior
  owners. If a governance suite stays, it must be tiny, durable, and have exit
  criteria.
- Core subprocess isolation helpers must not hide tests that are intended to
  exercise the real subprocess path. Any bypass must be opt-in, narrowly scoped,
  or explicitly excluded by stable marker/fixture semantics.
- Runtime/user state remains isolated: no repo-root `.runsight/`, `runsight.db`,
  `custom/`, real `.env`, shell credentials, or live third-party services.
- Use only targeted verification commands. Do not run full pytest, Vitest, or
  Playwright suites.

## Current Pre-Flight Findings

- The audit map and inventory match: 739 rows and no missing files on disk.
- The remaining GUI settings files are source-regex tests. They read
  `ProvidersTab.tsx`, `ModelsTab.tsx`, `SettingsPage.tsx`, and query/schema
  source files instead of rendering user-visible settings behavior.
- `apps/gui/src/features/settings` has no rendered settings owner suite yet.
  React Testing Library is already used in nearby GUI feature tests, so Tier 7
  should create rendered settings owners rather than preserve source scans.
- `testing/gui-e2e/tests/context-audit-flow.spec.ts` is route-mocked browser
  coverage. Lower-level context-audit GUI owners already exist under
  `apps/gui/src/features/surface/__tests__/`, so Tier 7 should first map which
  assertions are already covered before deciding whether to move, shrink, or
  delete the E2E spec.
- `packages/core/tests/test_exit_port_suite_ownership_governance.py` is an
  unfinished 1,041-line governance guard. It expects owner suites and
  `exit_port_helpers.py`, but the repo already has many focused exit/loop/output
  suites with different names. Tier 7 must map current coverage first and avoid
  creating duplicate suites only to satisfy stale guard shape.
- `packages/core/tests/conftest.py` has a global autouse subprocess-isolation
  bypass with filename-prefix exclusions. It is useful for parent-process mocks
  but risky because it can mask subprocess/runtime regressions if exclusions
  drift.
- The three API deep-review files mix behavior and governance/source-inspection
  styles. They are smaller than the core guard and should be resolved by either
  moving static checks to a durable governance owner, converting to behavior
  assertions, or confirming the existing suite is already the best owner.

## Recommended Worker Batches

### Batch A: GUI Settings Rendered Owners

Files:

- `apps/gui/src/features/settings/__tests__/modelsFallbackRows.test.ts`
- `apps/gui/src/features/settings/__tests__/modelsFallbackToggle.test.ts`
- `apps/gui/src/features/settings/__tests__/providersDeleteDialog.test.ts`
- `apps/gui/src/features/settings/__tests__/settingsAccessibility.test.ts`
- `apps/gui/src/features/settings/__tests__/settingsErrorStates.test.ts`

Expected owner target:

- Create one or two rendered behavior suites under
  `apps/gui/src/features/settings/__tests__/`, for example:
  - `settingsPageBehavior.test.tsx`
  - `settingsProviderManagement.test.tsx`
  - `settingsFallbackBehavior.test.tsx`
- Add package-local test builders/mocks only if needed, for example
  `settingsTestBuilders.tsx`.
- Delete the five source-regex suites once their behavior is covered by rendered
  tests.

Required behavior coverage:

- Settings navigation exposes Providers and Fallback tabs, not the old Models /
  Default Model section.
- Provider rows expose descriptive action labels for test/edit/delete and status
  / enable controls.
- Delete flow opens `DeleteConfirmDialog`, uses selected provider name/id,
  supports cancel, and passes pending state.
- Providers and fallback screens render retryable error states, call `refetch`,
  and disable/swap retry label while retrying.
- Fallback toggle reads and persists `fallback_enabled` through settings hooks.
- Fallback row behavior covers provider select, model select, clear action,
  disabled/unavailable states, and accessible labels.

Verification target:

```bash
pnpm -C apps/gui exec vitest run --config vitest.unit.config.ts src/features/settings/__tests__/<new-rendered-owner>.test.tsx
```

Primary risk: over-mocking UI primitives so the rendered tests become source
checks in disguise. Keep assertions user-visible and query by role/label/text.

### Batch B: E2E Context Audit Ownership

File:

- `testing/gui-e2e/tests/context-audit-flow.spec.ts`

Existing related lower-level owners:

- `apps/gui/src/features/surface/__tests__/contextAuditContract.test.ts`
- `apps/gui/src/features/surface/__tests__/contextAuditSurfaces.test.ts`
- `apps/gui/src/features/surface/__tests__/cubicContextAuditPanel.test.tsx`

Expected owner decision:

- Move route-mocked browser-contract assertions to a GUI-owned browser/component
  contract suite if lower-level owners do not already cover them.
- Keep at most one E2E smoke that uses the real E2E runtime root and live local
  harness route, not mocked API routes.
- Delete the route-mocked E2E spec if all behavior is already covered by GUI
  owners and no true E2E smoke is needed for this flow.

Verification target:

```bash
pnpm -C apps/gui exec vitest run --config vitest.unit.config.ts src/features/surface/__tests__/contextAuditSurfaces.test.tsx src/features/surface/__tests__/cubicContextAuditPanel.test.tsx
pnpm --dir testing/gui-e2e test -- tests/context-audit-flow.spec.ts --workers=1
```

Run the Playwright target only if the E2E file remains or is replaced by an E2E
smoke. Do not run the full Playwright suite.

Primary risk: moving true browser-only overflow/fork assertions too low. If a
browser layout invariant is retained, it should be a tiny smoke with explicit
isolation.

### Batch C: API Governance/Behavior Boundary Review

Files:

- `apps/api/tests/domain/test_sse_event_constants.py`
- `apps/api/tests/logic/test_run_repository_read_model_split.py`
- `apps/api/tests/unit/data/filesystem/test_workflow_repo_tool_governance.py`

Expected owner decisions:

- `test_sse_event_constants.py`: prefer behavior-owner coverage in event,
  streaming observer, and stream registry suites. Keep only minimal durable
  contract checks if source-inspection is still necessary for constants.
- `test_run_repository_read_model_split.py`: keep behavior tests that prove
  services require explicit `RunReadModel`; delete or shrink governance checks
  that inspect constructor/factory shape if constructors make bypass impossible.
- `test_workflow_repo_tool_governance.py`: keep repository behavior coverage for
  validation warnings/errors; move any static/governance-only checks to tooling
  or delete if covered by shared validation contract tests.

Verification targets:

```bash
uv run --package runsight pytest apps/api/tests/domain/test_sse_event_constants.py -q
uv run --package runsight pytest apps/api/tests/logic/test_run_repository_read_model_split.py -q
uv run --package runsight pytest apps/api/tests/unit/data/filesystem/test_workflow_repo_tool_governance.py -q
uv run --package runsight ruff check apps/api/tests/domain/test_sse_event_constants.py apps/api/tests/logic/test_run_repository_read_model_split.py apps/api/tests/unit/data/filesystem/test_workflow_repo_tool_governance.py
```

Primary risk: deleting governance assertions before behavior owners prove the
same invariant. Require a small coverage matrix before deletion.

### Batch D: Core Subprocess Isolation Fixture Boundary

File:

- `packages/core/tests/conftest.py`

Related contract:

- `packages/core/tests/test_conftest_isolation_mock.py`

Expected owner decision:

- Replace filename-prefix exclusion logic with a narrower, explicit fixture or
  marker where feasible.
- If global autouse remains, document and test the exact bypass/exclusion
  contract so new isolation tests cannot accidentally run through the in-process
  path.
- Keep temporary paths short for macOS socket limits without touching real user
  state.

Verification target:

```bash
uv run --package runsight-core pytest packages/core/tests/test_conftest_isolation_mock.py -q
uv run --package runsight-core ruff check packages/core/tests/conftest.py packages/core/tests/test_conftest_isolation_mock.py
```

Primary risk: breaking the large body of core tests that rely on parent-process
LLM mocks. Green should change this only after mapping current direct users of
`_bypass_subprocess_isolation` and isolation-specific exclusions.

### Batch E: Core Exit-Port Owner Suites And Guard Retirement

File:

- `packages/core/tests/test_exit_port_suite_ownership_governance.py`

Current related suites include:

- `packages/core/tests/test_exit_handle_all_block_types.py`
- `packages/core/tests/test_linearblock_exit_conditions.py`
- `packages/core/tests/test_loop_exports_contract.py`
- `packages/core/tests/test_nested_loop_exit_break.py`
- `packages/core/tests/unit/test_exit_handle_models.py`
- `packages/core/tests/unit/test_exit_output_condition_chains.py`
- `packages/core/tests/unit/test_exit_port_validation.py`
- `packages/core/tests/unit/test_exit_port_yaml_execution.py`
- `packages/core/tests/unit/test_exit_validation.py`
- `packages/core/tests/unit/test_gate_exit_handle.py`
- `packages/core/tests/unit/test_gate_exit_routing_integration.py`
- `packages/core/tests/unit/test_loop_exit_break_behavior.py`
- `packages/core/tests/unit/test_loop_exit_metadata_carry_context.py`
- `packages/core/tests/unit/test_loop_exit_retry_behavior.py`
- `packages/core/tests/unit/test_loop_exit_schema_parser.py`
- `packages/core/tests/unit/test_output_conditions_exit_handle_persistence.py`
- `packages/core/tests/unit/test_parser_delegate_exit_schema.py`
- `packages/core/tests/unit/test_resolve_next_exit_routing.py`

Expected owner decision:

- First map current focused exit-port coverage against the governance guard's
  expected behaviors.
- Add `packages/core/tests/exit_port_helpers.py` only if it reduces actual
  duplication in the current owner suites.
- Add or rename focused owner suites only for uncovered behavior. Do not create
  duplicate suites solely to satisfy old expected filenames.
- Delete or shrink `test_exit_port_suite_ownership_governance.py` after durable
  owner suites exist.

Verification target:

```bash
uv run --package runsight-core pytest packages/core/tests/test_exit_port_suite_ownership_governance.py -q
uv run --package runsight-core pytest packages/core/tests/unit/test_resolve_next_exit_routing.py packages/core/tests/unit/test_exit_output_condition_chains.py packages/core/tests/unit/test_loop_exit_break_behavior.py packages/core/tests/unit/test_loop_exit_retry_behavior.py -q
uv run --package runsight-core ruff check packages/core/tests/test_exit_port_suite_ownership_governance.py packages/core/tests/exit_port_helpers.py
```

Adjust the second command to the actual owner suites Green changes. Do not run
all core tests.

Primary risk: chasing the governance guard literally and creating duplicate
owners. Treat the guard as a failing review checklist, not as authoritative file
naming.

## RGB Gate Plan

For Tier 7, run RGB at batch level:

1. Red/analysis matrix: for each batch, map current assertions to intended owner
   behavior and identify deletion/replacement candidates.
2. Green implementation: apply each batch in parallel only when write sets are
   disjoint.
3. Blue review: targeted tests/lint, no source-scan regressions, no unsafe
   runtime state, no duplicate owner suites.
4. Yellow review: confirm the user goal is met: behavior-owned tests, no stale
   source scans, no permanent god/governance suites, no fake E2E.
5. Audit update: refresh inventory/map counts, mark resolved rows aligned, and
   update `SUMMARY.md`.

## Known Stop Conditions

Stop and ask before implementation if any of these are true:

- A rendered GUI settings owner cannot safely mount the settings components
  without changing product code.
- The route-mocked E2E spec contains a browser-only invariant not covered by GUI
  tests and no true E2E smoke path is available.
- Core exit-port current coverage conflicts with the governance guard's expected
  owner names enough that deleting the guard would remove the only executable
  review checklist.
- Narrowing core subprocess isolation would require broad full-suite validation.
