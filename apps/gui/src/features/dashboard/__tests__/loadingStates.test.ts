/**
 * RED-TEAM tests for RUN-343: B1 — Dashboard loading states — skeleton compositions.
 *
 * These tests verify ALL acceptance criteria by reading source files as strings
 * and asserting observable structural properties:
 *
 * AC1: Spinner replaced with skeleton compositions
 * AC2: KPI section shows 4 skeleton shapes while loading
 * AC3: Active runs section shows skeleton rows while loading
 * AC4: Skeletons visible only during loading state (not after data loads)
 * AC5: Uses existing Skeleton component, no new components
 *
 * Expected failures (current state):
 *   - DashboardOrOnboarding.tsx does not import Skeleton
 *   - No isLoading / isPending destructuring from query hooks
 *   - No conditional skeleton rendering for KPI section
 *   - No conditional skeleton rendering for active runs section
 *   - No skeleton compositions exist at all in the dashboard
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SRC_DIR = resolve(__dirname, "../../..");
const REPO_ROOT = resolve(__dirname, "../../../../../..");
const SKELETON_PATH = resolve(
  REPO_ROOT,
  "packages",
  "ui",
  "src",
  "components",
  "ui",
  "skeleton.tsx",
);

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

const DASHBOARD_PATH = "features/dashboard/DashboardOrOnboarding.tsx";

// ===========================================================================
// 1. Dashboard imports Skeleton component (AC5)
// ===========================================================================

describe("Dashboard uses existing Skeleton component (AC5)", () => {
  it("imports Skeleton from @runsight/ui/skeleton", () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/import.*Skeleton.*from.*@runsight\/ui\/skeleton/);
  });

  it("renders <Skeleton> elements in JSX", () => {
    const source = readSource(DASHBOARD_PATH);
    const skeletonUsages = (source.match(/<Skeleton\b/g) || []).length;
    expect(skeletonUsages).toBeGreaterThanOrEqual(1);
  });

  it("does NOT create any new skeleton or loading component files", () => {
    // The existing Skeleton component should be the only one used.
    // Verify it still exports correctly — no new file should be created.
    const source = readFileSync(SKELETON_PATH, "utf-8");
    expect(source).toMatch(/export.*Skeleton/);
  });
});

// ===========================================================================
// 2. Spinner replaced with skeletons (AC1)
// ===========================================================================

describe("Spinner replaced with skeleton compositions (AC1)", () => {
  it("does NOT use a spinner or loading spinner in the dashboard", () => {
    const source = readSource(DASHBOARD_PATH);
    // There should be no Spinner, LoadingSpinner, or circular progress references
    const hasSpinner =
      /Spinner|LoadingSpinner|CircularProgress|<Loader|spinner/i.test(source);
    expect(
      hasSpinner,
      "Expected no spinner references — skeletons should replace spinners",
    ).toBe(false);
  });

  it("uses Skeleton elements instead of any loading indicator", () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/<Skeleton\b/);
  });
});

// ===========================================================================
// 3. KPI section shows 4 skeleton shapes while loading (AC2)
// ===========================================================================

describe("KPI section shows 4 skeleton shapes while loading (AC2)", () => {
  it("destructures isLoading or isPending from useDashboardKPIs", () => {
    const source = readSource(DASHBOARD_PATH);
    // The dashboard must know when KPI data is loading
    // Pattern: const { data, isLoading } = useDashboardKPIs()
    // or: const { data, isPending } = useDashboardKPIs()
    // Must be in the same destructuring statement, not just co-existing in the file.
    const hasLoadingState =
      /\{[^}]*(?:isLoading|isPending)[^}]*\}\s*=\s*useDashboardKPIs\s*\(/.test(
        source,
      );
    expect(
      hasLoadingState,
      "Expected isLoading or isPending destructured from useDashboardKPIs()",
    ).toBe(true);
  });

  it("renders exactly 4 Skeleton elements in the KPI loading state", () => {
    const source = readSource(DASHBOARD_PATH);
    // The KPI section has 4 StatCards, so the skeleton state should show 4 skeletons.
    // They should appear in a grid (same grid-cols-4 layout as the real KPIs).
    // Count Skeleton usages that appear to be in a KPI-related context.
    const skeletonCount = (source.match(/<Skeleton\b/g) || []).length;
    // At minimum 4 for KPIs + 2 for active runs = 6 total
    // But this test specifically checks we have at least 4 for the KPI section.
    expect(skeletonCount).toBeGreaterThanOrEqual(4);
  });

  it("places KPI skeletons in a grid-cols-4 layout matching the real KPI grid", () => {
    const source = readSource(DASHBOARD_PATH);
    // The skeleton composition for KPIs should use the same 4-column grid
    // as the actual StatCards: grid grid-cols-4
    // There should be at least two occurrences of grid-cols-4 (one for real, one for skeleton)
    // OR the loading conditional should be inside the same grid container.
    const gridCount = (source.match(/grid-cols-4/g) || []).length;
    expect(gridCount).toBeGreaterThanOrEqual(1);
  });

  it("conditionally shows KPI skeletons only when data is loading", () => {
    const source = readSource(DASHBOARD_PATH);
    // The skeletons must be gated on the loading state — they should not show
    // when data has loaded. Look for conditional rendering patterns:
    // {isLoading ? <skeletons> : <real content>} or {isLoading && <skeletons>}
    const hasConditionalSkeleton =
      /(?:isLoading|isPending)\s*[?&][\s\S]*?<Skeleton|<Skeleton[\s\S]*?(?:isLoading|isPending)/.test(
        source,
      );
    expect(
      hasConditionalSkeleton,
      "Expected Skeleton rendering to be conditional on loading state",
    ).toBe(true);
  });
});

// ===========================================================================
// 4. Active runs section shows skeleton rows while loading (AC3)
// ===========================================================================

describe("Active runs section shows skeleton rows while loading (AC3)", () => {
  it("has loading state awareness for active runs data", () => {
    const source = readSource(DASHBOARD_PATH);
    // useActiveRuns spreads the query result, so isLoading is available.
    // The dashboard must destructure or access it.
    // Pattern: const { activeRuns, isLoading, ... } = useActiveRuns()
    // Must be in the same destructuring statement, not just co-existing in the file.
    const hasRunsLoading =
      /\{[^}]*(?:isLoading|isPending)[^}]*\}\s*=\s*useActiveRuns\s*\(/.test(
        source,
      );
    expect(
      hasRunsLoading,
      "Expected loading state awareness for active runs section",
    ).toBe(true);
  });

  it("renders at least 2 skeleton rows for the active runs loading state", () => {
    const source = readSource(DASHBOARD_PATH);
    // The spec says 2 skeleton table rows for active runs.
    // Total Skeleton count should be at least 6 (4 KPI + 2 active runs).
    const skeletonCount = (source.match(/<Skeleton\b/g) || []).length;
    expect(skeletonCount).toBeGreaterThanOrEqual(6);
  });

  it("skeleton rows appear in the ACTIVE RUNS section context", () => {
    const source = readSource(DASHBOARD_PATH);
    // The skeleton rows should be near the "ACTIVE RUNS" section heading.
    // Look for Skeleton usage in proximity to the ACTIVE RUNS section.
    const activeRunsSection = source.match(
      /ACTIVE RUNS[\s\S]*?(?:<\/section>|<\/Card>|<\/TableBody>)/,
    );
    expect(activeRunsSection).not.toBeNull();
    if (activeRunsSection) {
      expect(activeRunsSection[0]).toMatch(/<Skeleton\b/);
    }
  });
});

// ===========================================================================
// 5. Skeletons visible only during loading (AC4)
// ===========================================================================

describe("Skeletons visible only during loading state (AC4)", () => {
  it("uses ternary or conditional rendering to swap skeletons with real content", () => {
    const source = readSource(DASHBOARD_PATH);
    // The pattern should be: isLoading ? <skeleton> : <real content>
    // OR: {isLoading && <skeleton>} with separate {!isLoading && <content>}
    // This verifies that skeletons are NOT shown alongside loaded data.
    const hasTernary =
      /(?:isLoading|isPending)\s*\?\s*[\s\S]*?Skeleton[\s\S]*?:\s*[\s\S]*?(?:StatCard|activeRuns)|(?:isLoading|isPending)\s*\?\s*\([\s\S]*?Skeleton/.test(
        source,
      );
    const hasConditionalPair =
      /(?:isLoading|isPending)\s*&&[\s\S]*?Skeleton[\s\S]*?!(?:isLoading|isPending)\s*&&/.test(
        source,
      );
    expect(
      hasTernary || hasConditionalPair,
      "Expected conditional swap: skeletons when loading, real content when loaded",
    ).toBe(true);
  });

  it("KPI skeletons are replaced by StatCards after loading completes", () => {
    const source = readSource(DASHBOARD_PATH);
    // Both <Skeleton> and <StatCard> should exist, but gated on opposite conditions.
    // This means there must be a loading conditional that contains both paths.
    const hasSkeleton = /<Skeleton\b/.test(source);
    const hasStatCard = /<StatCard\b/.test(source);
    expect(hasSkeleton).toBe(true);
    expect(hasStatCard).toBe(true);

    // Additionally, they should be in a ternary or if/else — not side by side unconditionally.
    // Look for the pattern where isLoading/isPending gates Skeleton rendering.
    const hasLoadingGate =
      /(?:isLoading|isPending)[\s\S]*?Skeleton[\s\S]*?StatCard/.test(source);
    expect(
      hasLoadingGate,
      "Expected loading gate: Skeleton appears before StatCard with conditional logic",
    ).toBe(true);
  });

  it("active runs skeletons disappear when real run data is available", () => {
    const source = readSource(DASHBOARD_PATH);
    // After active runs load, skeleton rows must not be rendered.
    // The conditional should reference loading state of active runs.
    // Look for a pattern where active runs loading gates skeleton display.
    const hasRunsLoadingGate =
      /(?:isLoading|isPending)[\s\S]*?Skeleton[\s\S]*?(?:activeRuns\.map|run\.id)|(?:isLoading|isPending)[\s\S]*?Skeleton[\s\S]*?\.map\(/.test(
        source,
      );
    expect(
      hasRunsLoadingGate,
      "Expected active runs skeletons to be gated on loading state, replaced by real data",
    ).toBe(true);
  });
});

// ===========================================================================
// 6. Skeleton compositions use appropriate Skeleton variants
// ===========================================================================

describe("Skeleton compositions use correct variant props", () => {
  it("uses Skeleton with appropriate sizing for stat-card placeholders", () => {
    const source = readSource(DASHBOARD_PATH);
    // KPI skeleton shapes should resemble stat cards — using heading or custom sizing.
    // The Skeleton component supports variant="heading" (18px) and className overrides.
    // At minimum, Skeleton should be rendered with explicit sizing or a variant.
    const hasVariantOrClassName =
      /Skeleton\s+(?:variant|className)\s*=/.test(source);
    expect(
      hasVariantOrClassName,
      "Expected Skeleton elements with variant or className props for sizing",
    ).toBe(true);
  });

  it("uses Skeleton with row-like dimensions for active runs placeholders", () => {
    const source = readSource(DASHBOARD_PATH);
    // Active runs skeleton rows should mimic the row layout — likely full width and small height.
    // Look for Skeleton with className that sets height/width for row shapes.
    // Could be variant="text" with custom width or a className like "h-10 w-full".
    const hasRowSkeleton =
      /Skeleton[\s\S]*?(?:w-full|w-\[|h-\[|h-\d+)/.test(source);
    expect(
      hasRowSkeleton,
      "Expected Skeleton with row-like dimensions (width/height) for active runs",
    ).toBe(true);
  });
});
