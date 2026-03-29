# testing/gui-e2e

Workspace for GUI end-to-end verification.

Examples:

- Playwright specs
- E2E fixtures
- browser test helpers
- screenshot harness utilities used only for E2E

This workspace now owns:

- Playwright config
- E2E specs
- E2E setup/teardown helpers
- screenshot utilities used only for E2E/review flows

Current layout:

- `tests/` for the browser specs
- `global-setup.ts` and `global-teardown.ts` for workspace-level helpers
- `scripts/` for E2E-only utility scripts
