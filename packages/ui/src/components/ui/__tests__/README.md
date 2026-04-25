# packages/ui component test structure

RUN-977 establishes the rendered component baseline for the retained `@runsight/ui`
surface. New component behavior tests should use the local helpers from
`packages/ui/src/test/testUtils.tsx` instead of app-level test utilities.

## Rendered Baseline Suites

- `renderedDisplayContracts.test.tsx` covers display and data-display components: `Badge`, `StatusDot`, `RunStatusDot`, `EmptyState`, `Card`, `Skeleton`, `StatCard`, and `KeyValue`.
- `renderedFormControls.test.tsx` covers form and control components: `Button`, `Input`, `Label`, `Textarea`, `SegmentedControl`, `Switch`, `Slider`, and `TagInput`.
- `renderedNavigationAndOverlays.test.tsx` covers navigation, table, and overlay components: `Tabs`, `Table`, `Dialog`, `Select`, `DropdownMenu`, and `Tooltip`.
- `codeBlockCopy.test.tsx` is a focused rendered regression suite for `CodeBlock` copy behavior.
- `renderedCoverage.test.ts` enforces that every retained component export module, and every public named component export within those modules, is assigned to the rendered baseline.

## Static Guardrail Suites

The older `tier*`, `componentTokenSweep`, `supportedSurface`, and similar tests remain
as static policy checks for source ownership, token migration, package exports, and
Storybook presence. They should not be the only proof for rendered component behavior.
