/**
 * RED-TEAM tests for RUN-341: A6 — Attention section — end-to-end.
 *
 * These tests verify ALL frontend acceptance criteria by reading source files
 * as strings and asserting observable structural properties:
 *
 * AC1: "ATTENTION" section label (uppercase, mono, muted)
 * AC2: Section hidden when no attention items (conditional rendering)
 * AC3: Max 3 items shown, "see all" link for rest
 * AC4: Uses Card + Badge composition (imported, no new component)
 * AC5: Click navigates to relevant run/canvas
 * AC6: new_baseline items styled as informational (not warning)
 * AC7: useAttentionItems hook exists and calls /dashboard/attention
 *
 * Expected failures (current state):
 *   - DashboardOrOnboarding.tsx has no attention section
 *   - No useAttentionItems hook exists
 *   - No "ATTENTION" label anywhere in the dashboard
 *   - No Badge/Card composition for attention items
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SRC_DIR = resolve(__dirname, "../../..");
const SHARED_ZOD_PATH = resolve(
  __dirname,
  "../../../../../../packages/shared/src/zod.ts",
);

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

// ---------------------------------------------------------------------------
// File paths
// ---------------------------------------------------------------------------

const DASHBOARD_PATH = "features/dashboard/DashboardOrOnboarding.tsx";
const QUERIES_DASHBOARD_PATH = "queries/dashboard.ts";
const API_DASHBOARD_PATH = "api/dashboard.ts";
const QUERY_KEYS_PATH = "queries/keys.ts";

// ===========================================================================
// 1. "ATTENTION" section label (AC1)
// ===========================================================================

describe("ATTENTION section label (AC1)", () => {
  it("contains 'ATTENTION' text in the dashboard", () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/ATTENTION/);
  });

  it("uses monospace font for the ATTENTION label", () => {
    const source = readSource(DASHBOARD_PATH);
    // The ATTENTION label should be near a mono font class
    // Search for ATTENTION and mono in close proximity
    const hasAttentionMono =
      /font-mono[\s\S]{0,200}ATTENTION|ATTENTION[\s\S]{0,200}font-mono/.test(
        source,
      );
    expect(
      hasAttentionMono,
      "Expected ATTENTION label with mono font class",
    ).toBe(true);
  });

  it("uses muted text color for the ATTENTION label", () => {
    const source = readSource(DASHBOARD_PATH);
    const hasAttentionMuted =
      /text-muted[\s\S]{0,200}ATTENTION|ATTENTION[\s\S]{0,200}text-muted/.test(
        source,
      );
    expect(
      hasAttentionMuted,
      "Expected ATTENTION label with muted text color",
    ).toBe(true);
  });
});

// ===========================================================================
// 2. Section hidden when no attention items (AC2)
// ===========================================================================

describe("Section hidden when no attention items (AC2)", () => {
  it("conditionally renders the attention section", () => {
    const source = readSource(DASHBOARD_PATH);
    // Should have conditional rendering based on attention items length/existence
    const hasConditional =
      /attention.*&&|attention.*\.length|attentionItems.*&&|attentionItems.*\.length/.test(
        source,
      );
    expect(
      hasConditional,
      "Expected conditional rendering based on attention items data",
    ).toBe(true);
  });

  it("does not render ATTENTION label when items are empty", () => {
    const source = readSource(DASHBOARD_PATH);
    // The ATTENTION section must be guarded by a condition checking for items
    // Look for pattern like: {items.length > 0 && ( ... ATTENTION ... )}
    const hasGuardedAttention =
      /attentionItems\.length\s*>\s*0[\s\S]{0,400}ATTENTION|attentionItems\.length\s*&&[\s\S]{0,400}ATTENTION/.test(
        source,
      );
    expect(
      hasGuardedAttention,
      "Expected ATTENTION section to be conditionally rendered",
    ).toBe(true);
  });
});

// ===========================================================================
// 3. Max 3 items shown + "see all" link (AC3)
// ===========================================================================

describe("Max 3 items shown with 'see all' link (AC3)", () => {
  it("limits displayed attention items to 3", () => {
    const source = readSource(DASHBOARD_PATH);
    // Should have a .slice(0, 3) specifically in the attention items context
    const hasAttentionSlice =
      /attention[\s\S]{0,300}\.slice\s*\(\s*0\s*,\s*3\s*\)/.test(source);
    const hasAttentionLimit =
      /MAX_ATTENTION_ITEMS\s*=\s*3|ATTENTION_LIMIT\s*=\s*3/.test(source);
    expect(
      hasAttentionSlice || hasAttentionLimit,
      "Expected attention items limited to 3 (e.g. attentionItems.slice(0, 3))",
    ).toBe(true);
  });

  it("has a 'see all' link", () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/see all/i);
  });

  it("'see all' link includes arrow indicator", () => {
    const source = readSource(DASHBOARD_PATH);
    // The spec says "see all →"
    expect(source).toMatch(/see all\s*→|see all.*→/i);
  });
});

// ===========================================================================
// 4. Uses Card + Badge composition (AC4 — no new component)
// ===========================================================================

describe("Uses Card + Badge composition (AC4)", () => {
  it("imports Badge from components/ui/badge", () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/import.*Badge.*from.*badge/);
  });

  it("imports Card from components/ui/card and uses it in attention section", () => {
    const source = readSource(DASHBOARD_PATH);
    // Card must be used specifically within the attention items section (near ATTENTION label)
    expect(source).toMatch(/import.*Card.*from.*card/);
    // Card must be used in the context of attention items, not just elsewhere in dashboard
    const hasCardInAttention =
      /ATTENTION[\s\S]{0,800}<Card\b|attention[\s\S]{0,500}<Card\b/.test(source);
    expect(
      hasCardInAttention,
      "Expected Card component used within the ATTENTION section",
    ).toBe(true);
  });

  it("uses <Badge in JSX for attention items", () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/<Badge\b/);
  });

  it("uses <Card in JSX for attention items", () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/<Card\b/);
  });

  it("Badge is used with warning variant for attention items", () => {
    const source = readSource(DASHBOARD_PATH);
    // Badge should use warning variant for non-informational attention items
    expect(source).toMatch(/Badge[\s\S]{0,100}variant.*warning|variant.*warning[\s\S]{0,100}Badge/);
  });

  it("Card uses interactive variant for clickable attention items", () => {
    const source = readSource(DASHBOARD_PATH);
    // Card should be interactive for click navigation
    expect(source).toMatch(/Card[\s\S]{0,100}interactive|interactive[\s\S]{0,100}Card/);
  });
});

// ===========================================================================
// 5. Click navigates to relevant run/canvas (AC5)
// ===========================================================================

describe("Click navigates to relevant run detail (AC5)", () => {
  it("attention items have onClick handler", () => {
    const source = readSource(DASHBOARD_PATH);
    // Near the attention section, there should be an onClick
    // Since we already check for Card interactive, also check for navigate with run/workflow
    const hasAttentionClick =
      /attention[\s\S]{0,500}onClick|Card[\s\S]{0,100}onClick[\s\S]{0,300}workflow/.test(
        source,
      );
    expect(
      hasAttentionClick,
      "Expected onClick handler on attention items for navigation",
    ).toBe(true);
  });

  it("navigates using run_id from attention item", () => {
    const source = readSource(DASHBOARD_PATH);
    // Attention items should deep-link to the specific run for investigation.
    const hasAttentionNav =
      /\/runs\/\$\{item\.run_id\}|navigate\(\s*`\/runs\/\$\{item\.run_id\}`/.test(
        source,
      );
    expect(
      hasAttentionNav,
      "Expected attention item navigation using run_id to /runs/:id",
    ).toBe(true);
  });

  it("uses run_id context when navigating from attention item", () => {
    const source = readSource(DASHBOARD_PATH);
    const hasRunContext =
      /run_id[\s\S]{0,200}navigate|navigate[\s\S]{0,200}run_id|\/runs\/\$\{item\.run_id\}|\/runs\/\$\{.*run_id/.test(
        source,
      );
    expect(
      hasRunContext,
      "Expected run_id context used during attention item navigation",
    ).toBe(true);
  });
});

// ===========================================================================
// 6. new_baseline items styled as informational (AC6)
// ===========================================================================

describe("new_baseline items styled as informational (AC6)", () => {
  it("new_baseline uses info or neutral Badge variant (not warning)", () => {
    const source = readSource(DASHBOARD_PATH);
    // Should have conditional styling: new_baseline → info/neutral, others → warning
    const hasInfoVariant =
      /item\.type\s*===\s*["']new_baseline["'][\s\S]{0,200}["']info["']|isInfo[\s\S]{0,120}["']info["']/.test(
        source,
      );
    expect(
      hasInfoVariant,
      "Expected new_baseline items to use info or neutral variant",
    ).toBe(true);
  });

  it("distinguishes new_baseline from warning types in Badge variant", () => {
    const source = readSource(DASHBOARD_PATH);
    // Should have conditional: type === "new_baseline" ? "info" : "warning" or similar
    const hasConditionalVariant =
      /new_baseline.*\?.*["'](info|neutral)["'].*:.*["']warning["']|type.*===.*new_baseline/.test(
        source,
      );
    expect(
      hasConditionalVariant,
      "Expected conditional Badge variant for new_baseline vs warning types",
    ).toBe(true);
  });
});

// ===========================================================================
// 7. useAttentionItems hook (AC7)
// ===========================================================================

describe("useAttentionItems hook exists and is wired (AC7)", () => {
  it("queries/dashboard.ts exports a useAttentionItems function", () => {
    const source = readSource(QUERIES_DASHBOARD_PATH);
    expect(source).toMatch(/export\s+function\s+useAttentionItems/);
  });

  it("useAttentionItems calls /dashboard/attention endpoint", () => {
    const source = readSource(QUERIES_DASHBOARD_PATH);
    expect(source).toMatch(/dashboardApi\.getAttentionItems/);
  });

  it("Dashboard page imports useAttentionItems", () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/useAttentionItems/);
  });

  it("calls useAttentionItems() in the component", () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/useAttentionItems\s*\(/);
  });

  it("query keys include dashboard.attention", () => {
    const source = readSource(QUERY_KEYS_PATH);
    expect(source).toMatch(/attention/);
  });
});

// ===========================================================================
// 8. API layer and Zod schema wiring
// ===========================================================================

describe("API layer and Zod schema for attention items", () => {
  it("api/dashboard.ts exports a getAttention function", () => {
    const source = readSource(API_DASHBOARD_PATH);
    expect(source).toMatch(/getAttention|attention/i);
  });

  it("api/dashboard.ts calls /dashboard/attention endpoint", () => {
    const source = readSource(API_DASHBOARD_PATH);
    expect(source).toMatch(/\/dashboard\/attention/);
  });

  it("generated zod.ts exports AttentionItemsResponseSchema", () => {
    const source = readFileSync(SHARED_ZOD_PATH, "utf-8");
    expect(source).toMatch(/AttentionItem/);
  });
});

// ===========================================================================
// 9. Attention item structure in rendered output
// ===========================================================================

describe("Attention item card structure", () => {
  it("renders title for each attention item", () => {
    const source = readSource(DASHBOARD_PATH);
    // Should reference item.title or similar in the attention section
    const hasTitle = /\.title|item\.title|attention[\s\S]{0,500}title/.test(
      source,
    );
    expect(hasTitle, "Expected title rendered for attention items").toBe(true);
  });

  it("renders description for each attention item", () => {
    const source = readSource(DASHBOARD_PATH);
    const hasDescription =
      /\.description|item\.description|attention[\s\S]{0,500}description/.test(
        source,
      );
    expect(
      hasDescription,
      "Expected description rendered for attention items",
    ).toBe(true);
  });

  it("renders a warning icon (amber) for non-informational items", () => {
    const source = readSource(DASHBOARD_PATH);
    // Should import and use a warning icon (e.g. AlertTriangle, AlertCircle from lucide)
    const hasWarningIcon =
      /AlertTriangle|AlertCircle|TriangleAlert|warning.*icon|amber/.test(
        source,
      );
    expect(
      hasWarningIcon,
      "Expected warning icon for non-informational attention items",
    ).toBe(true);
  });
});
