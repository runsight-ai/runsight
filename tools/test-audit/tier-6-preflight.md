# Tier 6 Fixture Externalization Pre-Flight

Date: 2026-05-02

Status: completed. This file preserves the pre-flight scope snapshot; the
current audit counts live in `SUMMARY.md` and `full-test-cleanup-map.tsv`.

## Scope

Tier 6 is the fixture-externalization tier. It should not split suites, rename
behavior owners, or delete behavior coverage unless duplicate fixture-only
setup is discovered during the work.

Current audit state:

| Metric | Count |
|---|---:|
| Mapped test files | 739 |
| Aligned `KEEP` files | 684 |
| Tier 6 `EXTERNALIZE_FIXTURES` files | 44 |
| Later `REVIEW_DEEP` files | 11 |
| Remaining `SPLIT` files | 0 |

Workspace breakdown for Tier 6:

| Workspace | Files |
|---|---:|
| API | 30 |
| GUI | 12 |
| Core | 2 |

## Pre-Flight Findings

- The audit map and inventory match: 739 rows, no missing files on disk.
- No `SPLIT` rows remain.
- Static scan across Tier 6 files found no port/CWD-derived fallback pattern.
- Static scan found no direct real environment reads in Tier 6 files.
- Network-looking values are fixture URLs, mocked clients, or localhost-style
  harness values. Tier 6 must keep them mocked and must not add live service
  calls.
- Runtime-path literals such as `custom/`, `.runsight`, and `runsight.db` are
  currently test-path strings or `tmp_path` locations. Tier 6 must preserve that
  isolation and must not touch repo-root runtime state.
- `apps/api/tests/transport/test_attention.py` had a stale fixture plan of
  `none`; the map now points it at
  `apps/api/tests/transport/attention_helpers.py`.

## Tier 6 Definition Of Done

- Keep each behavior suite in place unless the file itself proves to be
  duplicate-only.
- Move repeated builders, large inline YAML/JSON, fake services, fake
  transports, static render harnesses, and repeated response payloads into the
  owning workspace.
- Do not hide assertions in helpers. Helpers should create data and harnesses;
  tests should still read as behavior checks.
- Prefer existing helpers before adding new ones.
- Use only targeted verification commands from
  `tools/test-audit/full-test-cleanup-map.tsv`.
- Do not run full pytest, Vitest, or Playwright suites.

## Existing Helpers To Reuse First

API helpers and fixture roots:

- `apps/api/tests/fixtures/`
- `apps/api/tests/logic/eval_observer_helpers.py`
- `apps/api/tests/logic/execution_preparation_helpers.py`
- `apps/api/tests/logic/save_commit_helpers.py`
- `apps/api/tests/logic/workflow_service_helpers.py`
- `apps/api/tests/sse_streaming_helpers.py`
- `apps/api/tests/transport/*_helpers.py`

GUI helpers:

- `apps/gui/src/features/surface/__tests__/helpers/genericBlockRoundTripHelpers.ts`
- `apps/gui/src/features/surface/__tests__/helpers/surfaceStreamTestHelpers.ts`
- `apps/gui/src/features/surface/__tests__/helpers/yamlCompilerFixtures.ts`

Core helpers and fixture roots:

- `packages/core/tests/fixtures/`
- `packages/core/tests/*_helpers.py`

## Recommended Worker Batches

### Batch A: API Repository And Settings Fixtures

Files:

- `apps/api/tests/data/test_base_yaml_repository.py`
- `apps/api/tests/data/test_filesystem.py`
- `apps/api/tests/data/test_snapshot_validation.py`
- `apps/api/tests/unit/core/test_secrets.py`
- `apps/api/tests/unit/data/filesystem/test_settings_repo.py`
- `apps/api/tests/unit/logic/test_settings_service.py`

Expected helper targets:

- `apps/api/tests/data/base_yaml_helpers.py`
- `apps/api/tests/data/filesystem_fixtures.py`
- `apps/api/tests/data/snapshot_validation_fixtures.py`
- `apps/api/tests/unit/core/secrets_helpers.py`
- `apps/api/tests/unit/data/filesystem/settings_repo_helpers.py`
- `apps/api/tests/unit/logic/settings_service_helpers.py`

Primary risk: accidentally moving temp `.runsight` or `custom/` semantics into
repo-root fixtures. Keep all filesystem writes under `tmp_path` or checked-in
test fixture directories.

### Batch B: API Execution, Runs, Branches, And Streams

Files:

- `apps/api/tests/logic/test_branch_aware_exec.py`
- `apps/api/tests/logic/test_execution_service_concurrency.py`
- `apps/api/tests/logic/test_execution_service_snapshot_resolution.py`
- `apps/api/tests/logic/test_nested_run_lifecycle.py`
- `apps/api/tests/logic/test_sim_branches.py`
- `apps/api/tests/logic/test_sse_streaming_service_events.py`
- `apps/api/tests/logic/test_stream_subscription.py`
- `apps/api/tests/logic/test_workflow_input_validation.py`
- `apps/api/tests/test_execution_transport_integration.py`
- `apps/api/tests/test_parser_warning_run_snapshots.py`

Expected helper targets:

- `apps/api/tests/logic/branch_execution_fixtures.py`
- `apps/api/tests/logic/execution_service_helpers.py`
- `apps/api/tests/logic/snapshot_resolution_fixtures.py`
- `apps/api/tests/logic/nested_run_helpers.py`
- `apps/api/tests/logic/sim_branch_helpers.py`
- `apps/api/tests/logic/sse_event_helpers.py`
- `apps/api/tests/logic/stream_subscription_helpers.py`
- `apps/api/tests/logic/workflow_input_validation_fixtures.py`
- `apps/api/tests/fixtures/execution_transport/`
- `apps/api/tests/fixtures/parser_warning_run_snapshots/`

Primary risk: moving setup into helpers that obscure the run lifecycle being
asserted. Keep lifecycle assertions in the test files.

### Batch C: API Provider, Eval, Regression, And Assertion Fixtures

Files:

- `apps/api/tests/logic/test_async_httpx.py`
- `apps/api/tests/logic/test_eval_observer_custom_assertion.py`
- `apps/api/tests/logic/test_eval_observer_transform.py`
- `apps/api/tests/logic/test_provider_service.py`
- `apps/api/tests/logic/test_regression_logic.py`
- `apps/api/tests/logic/test_wire_assertion_configs.py`
- `apps/api/tests/transport/test_eval_endpoints.py`
- `apps/api/tests/transport/test_eval_kpis.py`

Expected helper targets:

- `apps/api/tests/logic/provider_http_fixtures.py`
- `apps/api/tests/logic/eval_observer_helpers.py`
- `apps/api/tests/logic/provider_service_helpers.py`
- `apps/api/tests/logic/regression_fixtures.py`
- `apps/api/tests/logic/assertion_config_fixtures.py`
- `apps/api/tests/transport/eval_endpoint_helpers.py`
- `apps/api/tests/transport/eval_kpi_helpers.py`

Primary risk: fake provider and eval helpers can become miniature services.
Keep them as data builders or small fakes with explicit behavior.

### Batch D: API Transport Fixtures

Files:

- `apps/api/tests/transport/test_attention.py`
- `apps/api/tests/transport/test_git_file_read.py`
- `apps/api/tests/transport/test_sse_stream.py`
- `apps/api/tests/transport/test_workflow_simulation_input_schema_router.py`

Expected helper targets:

- `apps/api/tests/transport/attention_helpers.py`
- `apps/api/tests/transport/git_router_helpers.py`
- `apps/api/tests/transport/sse_stream_helpers.py`
- `apps/api/tests/transport/workflow_simulation_schema_helpers.py`

Primary risk: dependency override cleanup. Helpers may create overrides, but
the suite should still visibly clear them.

### Batch E: GUI Product Page Fixtures

Files:

- `apps/gui/src/features/dashboard/__tests__/activeRunsSection.test.ts`
- `apps/gui/src/features/git/__tests__/commitDialogSaveContract.test.ts`
- `apps/gui/src/features/runs/__tests__/runsPageContract.test.ts`
- `apps/gui/src/features/souls/__tests__/soulDeleteDialogContract.test.ts`
- `apps/gui/src/features/souls/__tests__/soulLibraryPageContract.test.ts`

Expected helper targets:

- dashboard test data builders
- commit dialog mock builders
- runs query and row builders
- souls dialog and library builders

Primary risk: static render mocks can hide UI behavior. Keep user-visible
assertions in the test files.

### Batch F: GUI Surface Fixtures

Files:

- `apps/gui/src/features/surface/__tests__/bottomPanelControllers.test.tsx`
- `apps/gui/src/features/surface/__tests__/genericBlockRoundTripContract.test.ts`
- `apps/gui/src/features/surface/__tests__/readonlySurfaceIntegration.test.tsx`
- `apps/gui/src/features/surface/__tests__/rerunWorkflowInputs.test.tsx`
- `apps/gui/src/features/surface/__tests__/runInputsModal.test.tsx`
- `apps/gui/src/features/surface/__tests__/saveCommitsToMain.test.ts`
- `apps/gui/src/features/surface/__tests__/sharedCanvasPath.test.tsx`

Expected helper targets:

- existing surface helpers under
  `apps/gui/src/features/surface/__tests__/helpers/`

Primary risk: reintroducing another broad surface helper that owns every test.
Prefer focused helpers for stream, canvas, run input schema, and save/commit
setup.

### Batch G: Core Assertion Fixtures

Files:

- `packages/core/tests/assertions/test_custom_adapter.py`
- `packages/core/tests/test_custom_assertion_registration.py`

Expected helper targets:

- package-local assertion helper modules
- package-local checked-in custom assertion snippets where inline source is
  currently repeated

Primary risk: subprocess/import-blocking cases must stay in-memory or `tmp_path`
and must not depend on user-authored `custom/`.

## Gate Sequence For Tier 6

For each batch:

1. Green externalizes fixtures inside the owning workspace only.
2. Green runs the targeted commands from the map for changed files.
3. Blue verifies no behavior was hidden in helpers, no real state/network was
   introduced, and targeted tests pass.
4. Yellow verifies the suite still communicates behavior clearly and does not
   become helper-driven ceremony.
5. The audit map is refreshed and the batch is committed before moving on.
