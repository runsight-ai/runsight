# testing/gui-e2e

Workspace for GUI end-to-end verification.

Examples:

- Playwright specs
- E2E fixtures
- browser test helpers

This workspace now owns:

- Playwright config
- E2E specs

Current layout:

- `playwright.config.ts` for the active Playwright harness configuration
- `tests/` for the browser specs

The retained harness surface is intentionally small:

- Playwright starts the GUI dev server through `webServer`
- Specs assume the API is already available on `http://localhost:8000`
