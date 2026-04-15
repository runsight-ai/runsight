# Repository Structure Policy

This file is the authoritative repo-layout guide for agents and contributors.

The old orchestration instructions that previously lived here are obsolete.
Use this file to decide where new code belongs, what should be moved during
refactors, and which boundaries must stay clean over time.

## Why This Structure Exists

Runsight currently mixes product app code, design-system code, generated
contracts, test harnesses, and developer tooling too closely. That makes it
easy to put new files in the wrong place and hard to tell what is runtime code
 versus support code.

The target structure separates:

- product runtimes
- reusable packages
- verification workspaces
- developer tooling
- custom runtime assets

This keeps `apps/gui` focused on the actual product, keeps shared contracts out
of app code, and prevents Storybook and E2E infrastructure from growing inside
the GUI runtime.

## Target Repo Layout

```text
apps/
  api/
  gui/

packages/
  core/
  shared/
  ui/

testing/
  gui-e2e/

tools/

custom/
  tools/
  providers/
  souls/
  workflows/
```

## Workspace Responsibilities

### `apps/api`

Backend service only.

Allowed here:

- FastAPI routes, transport schemas, service wiring
- backend persistence, observers, API-specific logic
- backend tests that belong to the API workspace

Do not put here:

- frontend contracts that should be shared with the GUI
- reusable runtime engine code
- Storybook, browser tests, or design-system code

### `apps/gui`

Product application only.

Allowed here:

- routes
- product features and screens
- app state
- product-specific queries and API adapters
- product-only components

Do not put here:

- Storybook stories or Storybook config
- design-system primitives that should be reusable
- generated shared contracts
- browser E2E harnesses
- general-purpose developer tools

Rule of thumb:

- If a component exists only because the product app needs it, it belongs in
  `apps/gui`.
- If a component is a reusable primitive or shared visual building block, it
  belongs in `packages/ui`.

### `packages/core`

Reusable workflow/runtime engine code.

Allowed here:

- domain runtime primitives
- execution engine building blocks
- reusable workflow parsing/execution logic
- core package tests

Canonical home for the reusable Runsight runtime engine.

### `packages/shared`

Shared contracts only.

Allowed here:

- zod schemas
- generated OpenAPI types
- DTOs
- shared enums
- request/response contract helpers

Do not put here:

- backend business logic
- frontend app state
- UI components
- browser-only helpers

Rule of thumb:

- If both `apps/api` and `apps/gui` must agree on it structurally, it probably
  belongs in `packages/shared`.
- If only one side imports it, it probably does not belong here.

### `packages/ui`

Design system and reusable UI building blocks.

Allowed here:

- UI primitives such as `Button`, `Dialog`, `Tabs`
- shared visual components
- tokens and design-system assets
- Storybook stories
- Storybook configuration

Do not put here:

- product routes
- workflow pages
- app-specific dashboard sections
- backend or contract logic

### `testing/gui-e2e`

Standalone browser verification workspace.

Allowed here:

- Playwright config
- E2E fixtures and helpers
- browser/system tests
- screenshot and harness utilities used only for E2E verification
- local generated reports such as `playwright-report/` and `test-results/`

Do not put here:

- product runtime code
- reusable UI primitives
- backend test suites that belong to `apps/api` or `packages/core`

### `tools`

Developer tooling and repo machinery.

Allowed here:

- code generation scripts
- migration scripts
- codemods
- local CLIs
- repo maintenance and validation scripts

## Generated Output Policy

Generated artifacts should live next to the workspace that produces them and
must be git-ignored there.

Examples:

- `apps/api/dist`
- `apps/gui/dist`
- `packages/ui/storybook-static`
- `testing/gui-e2e/playwright-report`
- `testing/gui-e2e/test-results`

Do not leave generated artifacts in legacy source locations after moving a
workspace. Delete obsolete directories instead of keeping compatibility
placeholders.

Current migration note:

- The current legacy location is `scripts/`.
- New tooling should prefer the `tools/` target model.

### `custom`

User-authored or runtime-authored assets that are not source packages.

Allowed here:

- custom/tools/ metadata and helper code assets
- custom providers
- souls
- workflows
- workflow canvas state artifacts if intentionally kept as custom assets

Do not mix `custom/` with package source code.

## Test Placement Rules

Tests should follow ownership:

- API tests stay with `apps/api`
- core package tests stay with `packages/core` or the legacy `libs/core` until
  migrated
- package-level unit tests stay with the package they verify
- cross-app browser/system tests go in `testing/gui-e2e`

Do not use `testing/` as a dumping ground for every test in the repo.
`testing/` is for harness-style verification workspaces, not ordinary unit
tests.

## Migration Map From Current Layout

These are the important canonical homes.

- `packages/ui` is the canonical home for reusable UI primitives, stories, and Storybook config.
- `packages/shared` is the canonical home for generated OpenAPI contracts and shared Zod schemas.
- `testing/gui-e2e` is the canonical home for Playwright config and browser-system specs.
- `tools` is the canonical home for repo tooling and codegen scripts.
- `packages/core` is the canonical home for the runtime engine package.

## Hard Boundary Rules

- Do not add new Storybook stories under `apps/gui/src`.
- Do not add new E2E specs under `apps/gui`.
- Do not recreate `apps/gui/src/types/generated`.
- Do not recreate `libs/core`.
- Do not add new reusable runtime code under `apps/api`.
- Do not recreate `scripts/`.
- Do not turn `packages/shared` into a junk drawer for logic that is not truly
  shared.

## How To Decide Where New Code Goes

Ask these questions in order:

1. Is this a deployable/runtime app concern?
   If yes, it belongs in `apps/api` or `apps/gui`.
2. Is this imported by multiple workspaces as reusable code?
   If yes, it belongs in `packages/*`.
3. Is this a verification harness rather than app/runtime code?
   If yes, it belongs in `testing/*`.
4. Is this developer/build/codegen machinery?
   If yes, it belongs in `tools/`.
5. Is this a custom runtime asset rather than source code?
   If yes, it belongs in `custom/`.

If the answer is still unclear, prefer the stricter boundary and document the
decision in the change.

## Release Process

**Every PR that changes behavior must bump the version** in the root `pyproject.toml`.

The `version` field in `pyproject.toml` (repo root) is the **single source of truth**. When a PR merges to main and the version has changed, CI automatically:
1. Publishes both `runsight` and `runsight-core` to PyPI
2. Builds and pushes Docker image to GHCR
3. Creates a git tag `v{version}`

Do NOT create git tags manually. Do NOT modify version fields in `apps/api/pyproject.toml` or `packages/core/pyproject.toml` — CI handles those.

## Key Rules

- Never run full test suites (pytest or vitest) — they consume ~4GB each and hang the machine. Target specific files only.
- Styling: CVA + Tailwind + @theme tokens. No BEM, no mixing approaches.
- Main branch = production. Simulation branches for testing uncommitted changes.

## Codebones

This project is indexed by codebones. Prefer codebones tools over file crawling:

- `codebones search <name>` — find functions/classes by name
- `codebones get <symbol> --filter <keyword>` — read matching lines only (cheap)
- `codebones get <symbol>` — read full source (when you need the complete implementation)
- `codebones outline <file>` — see file structure (signatures, bodies elided)
- `codebones graph <file>` — blast radius: what depends on this file and what they import
