# packages/ui component test structure

Component behavior tests for the retained `@runsight/ui` surface use package-local
helpers from `packages/ui/src/test/testUtils.tsx`, not app-level test utilities.

## Rendered Baseline Suites

- `renderedDisplayContracts.test.tsx` covers display and data-display components: `Badge`, `StatusDot`, `RunStatusDot`, `EmptyState`, `Card`, `Skeleton`, `StatCard`, and `KeyValue`.
- `renderedFormControls.test.tsx` covers form and control components: `Button`, `Input`, `Label`, `Textarea`, `SegmentedControl`, `Switch`, `Slider`, and `TagInput`.
- `renderedTabsAndTables.test.tsx` covers `Tabs` and `Table` rendered behavior.
- `renderedOverlayPrimitives.test.tsx` covers overlay components: `Dialog`, `Select`, `DropdownMenu`, and `Tooltip`.
- `codeBlockCopy.test.tsx` is a focused rendered regression suite for `CodeBlock` copy behavior.
- `renderedCoverage.test.ts` enforces that every retained component export module, and every public named component export within those modules, is assigned to the rendered baseline.

## Static Guardrail Suites

- `corePrimitiveContracts.test.ts`, `feedbackPrimitiveContracts.test.ts`,
  `formControlContracts.test.ts`, `dataDisplayContracts.test.ts`,
  `navigationContracts.test.ts`, and `overlayContracts.test.ts` own static
  component source contracts.
- `componentTokenSweep.test.ts` owns package component token-source policy.
- `supportedSurface.test.ts` owns package export-surface policy only.
- `publicExportSurfaceOwnership.test.ts` prevents package export tests from
  reabsorbing GUI import scanning or Storybook story ownership.
- Storybook presence and scenarios live under `packages/ui/src/stories/__tests__`.

Static policy checks should not be the only proof for rendered component behavior.
