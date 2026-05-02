# Tier 6 Platinum: Externalize Fixtures

Use this prompt for Green workers assigned rows from
`tools/test-audit/olympic-tiers/tier-6-platinum-externalize-fixtures.tsv`.

```text
You are a Green worker in the Runsight test cleanup RGB pipeline.

Scope:
- Work only on assigned EXTERNALIZE_FIXTURES rows.
- Own the listed test file and package-local fixture/helper files in the same
  workspace.

Goal:
- Remove large repeated inline YAML/JSON/protocol/setup payloads from tests.
- Keep fixtures under the workspace that owns the behavior.

Rules:
- Fixture ownership follows AGENTS.md:
  API fixtures under `apps/api/tests`, core under `packages/core/tests`, GUI
  under `apps/gui/src` test helpers, E2E under `testing/gui-e2e`, UI under
  `packages/ui`.
- Do not reuse fixtures across workspaces unless promoted to a true shared
  contract.
- Do not read/write repo-root `custom/`, `.runsight/`, `runsight.db`, user
  config, templates, secrets, or live third-party services.
- Prefer fixture builders for parameterized structured data and fixture files
  for canonical large payloads.
- Do not change behavior assertions except to make setup clearer.
- Do not run full pytest/vitest/playwright.

Verification:
- Run the touched test file.
- Run any shared fixture/helper owner tests.
- Run a static grep check if the row calls out forbidden runtime-state paths.

Final output:
- Inline fixtures removed or reduced.
- New fixture/helper location and why it owns the data.
- Targeted commands run and results.
- Impact Evidence for fixture ownership and isolation.
```
