/**
 * RED-TEAM tests for RUN-356: T1 — Topbar layout + workflow name (editable) + Canvas|YAML toggle.
 *
 * These tests verify the structural acceptance criteria by reading source
 * files and asserting observable properties:
 *
 * AC1: Route /workflows/:id/edit exists and renders CanvasPage
 * AC2: Topbar renders at correct height (var(--header-height))
 * AC3: Workflow name displayed and editable (click -> input -> blur saves)
 * AC4: Canvas|YAML toggle visible (Canvas tab disabled with tooltip "Coming soon")
 * AC5: Placeholder slots for Save and Run (right side)
 * AC6: Uses Tabs component from component library
 * AC7: Uses design system tokens only
 *
 * Expected failures (current state):
 *   - No CanvasPage.tsx or CanvasTopbar.tsx components exist
 *   - No /workflows/:id/edit route in routes/index.tsx
 *   - WorkflowCanvas.tsx is the old component with no topbar
 */

import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SRC_DIR = resolve(__dirname, "../../..");

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

function fileExists(relativePath: string): boolean {
  return existsSync(resolve(SRC_DIR, relativePath));
}

// ---------------------------------------------------------------------------
// File paths
// ---------------------------------------------------------------------------

const ROUTES_PATH = "routes/index.tsx";
const CANVAS_PAGE_PATH = "features/canvas/CanvasPage.tsx";
const CANVAS_TOPBAR_PATH = "features/canvas/CanvasTopbar.tsx";

// ===========================================================================
// 1. Route /workflows/:id/edit exists and renders CanvasPage (AC1)
// ===========================================================================

describe("Route /workflows/:id/edit exists (AC1)", () => {
  let source: string;

  it("CanvasPage.tsx file exists", () => {
    expect(
      fileExists(CANVAS_PAGE_PATH),
      "Expected features/canvas/CanvasPage.tsx to exist",
    ).toBe(true);
  });

  it("CanvasTopbar.tsx file exists", () => {
    expect(
      fileExists(CANVAS_TOPBAR_PATH),
      "Expected features/canvas/CanvasTopbar.tsx to exist",
    ).toBe(true);
  });

  it("routes/index.tsx has a route for workflows/:id/edit", () => {
    source = readSource(ROUTES_PATH);
    expect(source).toMatch(/workflows\/:id\/edit/);
  });

  it("the edit route lazy-imports CanvasPage", () => {
    source = readSource(ROUTES_PATH);
    // Should have: import("@/features/canvas/CanvasPage") in the edit route
    expect(source).toMatch(/canvas\/CanvasPage/);
  });

  it("the old workflows/:id route still exists (renders WorkflowCanvas)", () => {
    source = readSource(ROUTES_PATH);
    // Verify the old route is preserved alongside the new one
    expect(source).toMatch(/canvas\/WorkflowCanvas/);
    expect(source).toMatch(/path:\s*["']workflows\/:id["']/);
  });
});

// ===========================================================================
// 2. CanvasPage component structure
// ===========================================================================

describe("CanvasPage component structure", () => {
  it("CanvasPage exports a Component (lazy-route compatible)", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+Component/);
  });

  it("CanvasPage renders CanvasTopbar", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/<CanvasTopbar/);
  });

  it("CanvasPage extracts id from route params via useParams", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/useParams/);
  });
});

// ===========================================================================
// 3. Topbar height uses --header-height token (AC2)
// ===========================================================================

describe("Topbar height uses --header-height (AC2)", () => {
  it("CanvasTopbar uses h-[var(--header-height)]", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    expect(source).toMatch(/h-\[var\(--header-height\)\]/);
  });

  it("CanvasTopbar does NOT use hardcoded height values (h-10, h-12, h-40px)", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // Should not have hardcoded heights — only the CSS variable
    expect(source).not.toMatch(/\bh-10\b/);
    expect(source).not.toMatch(/\bh-12\b/);
    expect(source).not.toMatch(/h-\[40px\]/);
  });
});

// ===========================================================================
// 4. Workflow name — displayed and editable (AC3)
// ===========================================================================

describe("Workflow name editable (AC3)", () => {
  let source: string;

  it("imports useWorkflow hook to fetch workflow data", () => {
    source = readSource(CANVAS_TOPBAR_PATH);
    expect(source).toMatch(/import.*useWorkflow.*from/);
  });

  it("imports useUpdateWorkflow hook for saving name changes", () => {
    source = readSource(CANVAS_TOPBAR_PATH);
    expect(source).toMatch(/import.*useUpdateWorkflow.*from/);
  });

  it("has an input element for inline editing the name", () => {
    source = readSource(CANVAS_TOPBAR_PATH);
    // Should have an <input> for editing workflow name
    expect(source).toMatch(/<input/);
  });

  it("handles blur event to save the name (PUT /api/workflows/:id)", () => {
    source = readSource(CANVAS_TOPBAR_PATH);
    // Should have onBlur handler that triggers the update mutation
    expect(source).toMatch(/onBlur/);
  });

  it("handles Enter key to save the name", () => {
    source = readSource(CANVAS_TOPBAR_PATH);
    // Should handle Enter keypress to commit the edit
    expect(source).toMatch(/Enter|onKeyDown|onKeyUp/);
  });

  it("has click-to-edit behavior (editing state toggle)", () => {
    source = readSource(CANVAS_TOPBAR_PATH);
    // Should have a state variable for tracking edit mode
    const hasEditState =
      /isEditing|editing|setEditing|setIsEditing/.test(source);
    expect(
      hasEditState,
      "Expected editing state variable (isEditing/editing)",
    ).toBe(true);
  });
});

// ===========================================================================
// 5. Canvas|YAML toggle (AC4)
// ===========================================================================

describe("Canvas|YAML toggle (AC4)", () => {
  let source: string;

  it("imports Tabs components from component library", () => {
    source = readSource(CANVAS_TOPBAR_PATH);
    expect(source).toMatch(/import.*Tabs.*from.*components\/ui\/tabs/);
  });

  it("renders TabsList with contained variant", () => {
    source = readSource(CANVAS_TOPBAR_PATH);
    // The toggle should use the "contained" variant for a pill/segment look
    expect(source).toMatch(/variant\s*=\s*["']contained["']/);
  });

  it("has a 'Canvas' tab trigger", () => {
    source = readSource(CANVAS_TOPBAR_PATH);
    expect(source).toMatch(/Canvas/);
    expect(source).toMatch(/TabsTrigger/);
  });

  it("has a 'YAML' tab trigger", () => {
    source = readSource(CANVAS_TOPBAR_PATH);
    expect(source).toMatch(/YAML/);
  });

  it("Canvas tab is disabled", () => {
    source = readSource(CANVAS_TOPBAR_PATH);
    // The Canvas tab should have disabled prop
    // Pattern: <TabsTrigger ... disabled ...>Canvas</TabsTrigger>
    expect(source).toMatch(/disabled/);
  });

  it("YAML tab is active by default", () => {
    source = readSource(CANVAS_TOPBAR_PATH);
    // Default value for Tabs should be "yaml" or the YAML tab value
    expect(source).toMatch(/defaultValue\s*=\s*["']yaml["']|value.*yaml/i);
  });

  it("Canvas tab has 'Coming soon' tooltip", () => {
    source = readSource(CANVAS_TOPBAR_PATH);
    expect(source).toMatch(/Coming soon/);
  });

  it("imports Tooltip components for the disabled Canvas tab", () => {
    source = readSource(CANVAS_TOPBAR_PATH);
    expect(source).toMatch(/import.*Tooltip.*from.*components\/ui\/tooltip/);
  });
});

// ===========================================================================
// 6. Placeholder slots for Save and Run buttons (AC5)
// ===========================================================================

describe("Placeholder slots for Save and Run (AC5)", () => {
  let source: string;

  it("has a placeholder or slot for a Save button", () => {
    source = readSource(CANVAS_TOPBAR_PATH);
    // Should have Save text or a save placeholder
    expect(source).toMatch(/Save/i);
  });

  it("has a placeholder or slot for a Run button", () => {
    source = readSource(CANVAS_TOPBAR_PATH);
    // Should have Run text or a run placeholder
    expect(source).toMatch(/Run/);
  });

  it("right section exists (flex container for action buttons)", () => {
    source = readSource(CANVAS_TOPBAR_PATH);
    // The right side should have a flex container grouping action slots
    // Typically: flex items-center gap-* at the end of the topbar
    const hasRightSection =
      /ml-auto|justify-end|flex-1.*justify-end|right.*slot|actions/.test(source);
    expect(
      hasRightSection,
      "Expected a right-aligned section for action button slots",
    ).toBe(true);
  });
});

// ===========================================================================
// 7. Design system tokens only (AC7)
// ===========================================================================

describe("Uses design system tokens only (AC7)", () => {
  it("CanvasTopbar does NOT use hardcoded hex colors", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // Should not have any inline hex colors like #fff, #1a1a1a, etc.
    // Allow # in CSS variable references like var(--something)
    const hexMatches = source.match(/#[0-9a-fA-F]{3,8}\b/g);
    const filteredHex = hexMatches?.filter(
      (m) => !/^#[0-9a-fA-F]{6}$/.test(m) || true,
    );
    // All color values should come from CSS variables/tokens
    expect(hexMatches).toBeNull();
  });

  it("CanvasTopbar does NOT use hardcoded rgba colors", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    expect(source).not.toMatch(/rgba?\s*\(\s*\d+/);
  });

  it("CanvasTopbar uses border token (border-border-subtle or similar)", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // The topbar should use a bottom border with design system tokens
    const hasBorderToken =
      /border-border|border-\(--.*\)|border-b/.test(source);
    expect(
      hasBorderToken,
      "Expected border using design system tokens",
    ).toBe(true);
  });
});

// ===========================================================================
// 8. Three-section layout (left, center, right)
// ===========================================================================

describe("Topbar three-section layout", () => {
  it("CanvasTopbar has a logo/icon on the left", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    // Should import a logo icon or have a logo element
    const hasLogo = /logo|Logo|icon.*logo|Braces|Command|Workflow/i.test(source);
    expect(
      hasLogo,
      "Expected a logo or icon element in the left section",
    ).toBe(true);
  });

  it("CanvasTopbar layout uses flexbox with items-center", () => {
    const source = readSource(CANVAS_TOPBAR_PATH);
    expect(source).toMatch(/flex/);
    expect(source).toMatch(/items-center/);
  });
});
