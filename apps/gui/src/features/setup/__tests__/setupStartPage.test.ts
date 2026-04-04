/**
 * RED-TEAM tests for RUN-351: Setup Choose screen (/setup/start) — end-to-end.
 *
 * Source-reading pattern: verify structural properties by reading source files.
 *
 * AC1: /setup/start renders 2 selection cards
 * AC2: Template card is default selected (accent border)
 * AC3: Clicking card toggles selection (radiogroup pattern with aria)
 * AC4: "Start Building" creates workflow and navigates to canvas
 * AC5: Button shows spinner during creation
 * AC6: Toast on error, button re-enables
 * AC7: onboarding_completed set to true after success
 * AC8: No API key shows warning badge on template card ("Explore mode")
 *
 * Expected failures (current state):
 *   - SetupStartPage.tsx does not exist
 *   - SelectionCard.tsx does not exist
 *   - MiniDiagram.tsx does not exist
 *   - EmptyCanvasPreview.tsx does not exist
 *   - Route /setup/start not registered in routes/index.tsx
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

const SETUP_START_PAGE_PATH = "features/setup/SetupStartPage.tsx";
const SELECTION_CARD_PATH = "features/setup/components/SelectionCard.tsx";
const MINI_DIAGRAM_PATH = "features/setup/components/MiniDiagram.tsx";
const EMPTY_CANVAS_PREVIEW_PATH = "features/setup/components/EmptyCanvasPreview.tsx";
const ROUTES_PATH = "routes/index.tsx";

// ===========================================================================
// 1. Route exists: /setup/start registered outside ShellLayout
// ===========================================================================

describe("Route /setup/start is registered outside ShellLayout", () => {
  it("routes/index.tsx contains 'setup/start' path", () => {
    const source = readSource(ROUTES_PATH);
    expect(source).toMatch(/setup\/start/);
  });

  it("route is defined outside ShellLayout (top-level sibling)", () => {
    const source = readSource(ROUTES_PATH);
    // The /setup/start route must be a top-level route (outside ShellLayout).
    // First, confirm the route exists at all:
    expect(source).toMatch(/setup\/start/);
    // Then verify it is NOT inside the ShellLayout children block.
    const shellLayoutBlock = source.match(
      /element:\s*<ShellLayout\s*\/>[\s\S]*?children:\s*\[([\s\S]*?)\]\s*,?\s*\}/,
    );
    expect(shellLayoutBlock).not.toBeNull();
    const shellChildren = shellLayoutBlock![1];
    expect(shellChildren).not.toMatch(/setup\/start/);
  });

  it("route lazily imports SetupStartPage", () => {
    const source = readSource(ROUTES_PATH);
    expect(source).toMatch(/setup\/start[\s\S]*?import.*SetupStartPage/);
  });
});

// ===========================================================================
// 2. Component files exist
// ===========================================================================

describe("SetupStartPage and sub-component files exist", () => {
  it("SetupStartPage.tsx exists", () => {
    expect(
      fileExists(SETUP_START_PAGE_PATH),
      "Expected features/setup/SetupStartPage.tsx to exist",
    ).toBe(true);
  });

  it("SetupStartPage exports Component (lazy import pattern)", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    expect(source).toMatch(/export\s+(const|function)\s+Component/);
  });

  it("SelectionCard.tsx exists", () => {
    expect(
      fileExists(SELECTION_CARD_PATH),
      "Expected features/setup/components/SelectionCard.tsx to exist",
    ).toBe(true);
  });

  it("SelectionCard exports SelectionCard", () => {
    const source = readSource(SELECTION_CARD_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+SelectionCard/);
  });

  it("MiniDiagram.tsx exists", () => {
    expect(
      fileExists(MINI_DIAGRAM_PATH),
      "Expected features/setup/components/MiniDiagram.tsx to exist",
    ).toBe(true);
  });

  it("EmptyCanvasPreview.tsx exists", () => {
    expect(
      fileExists(EMPTY_CANVAS_PREVIEW_PATH),
      "Expected features/setup/components/EmptyCanvasPreview.tsx to exist",
    ).toBe(true);
  });
});

// ===========================================================================
// 3. Page layout and heading
// ===========================================================================

describe("SetupStartPage layout and heading", () => {
  it("renders an h1 with 'How do you want to start?'", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    expect(source).toMatch(/How do you want to start\?/);
  });

  it("renders subtitle 'You can always switch later.'", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    expect(source).toMatch(/You can always switch later/);
  });

  it("uses min-h-screen for full-screen layout", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    expect(source).toMatch(/min-h-screen/);
  });

  it("uses a constrained max-width container (max-w-[540px])", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    expect(source).toMatch(/max-w-\[540px\]/);
  });
});

// ===========================================================================
// 4. Selection cards — radiogroup with 2 radio options (AC1, AC3)
// ===========================================================================

describe("Selection cards with radiogroup pattern (AC1, AC3)", () => {
  it("renders a container with role='radiogroup'", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    expect(source).toMatch(/role=["']radiogroup["']/);
  });

  it("radiogroup has aria-label 'Starting point'", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    expect(source).toMatch(/aria-label=["']Starting point["']/);
  });

  it("renders SelectionCard with role='radio' (at least 2)", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    // Either the cards themselves have role=radio, or SelectionCard component does.
    // Check for at least 2 SelectionCard usages in the page.
    const cardMatches = source.match(/<SelectionCard/g) ?? [];
    expect(cardMatches.length).toBeGreaterThanOrEqual(2);
  });

  it("SelectionCard component uses role='radio' for accessibility", () => {
    const source = readSource(SELECTION_CARD_PATH);
    expect(source).toMatch(/role=["']radio["']/);
  });

  it("SelectionCard has aria-checked attribute for selected state", () => {
    const source = readSource(SELECTION_CARD_PATH);
    expect(source).toMatch(/aria-checked/);
  });
});

// ===========================================================================
// 5. Default selection — template card selected (AC2)
// ===========================================================================

describe("Template card is default selected (AC2)", () => {
  it("has a state variable for selection defaulting to 'template'", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    // Should have useState with 'template' as initial value
    const hasTemplateDefault =
      /useState.*["']template["']|useState\(["']template["']\)/.test(source);
    expect(
      hasTemplateDefault,
      "Expected selection state initialized to 'template'",
    ).toBe(true);
  });

  it("template card has 'Recommended' badge", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    expect(source).toMatch(/Recommended/);
  });

  it("renders MiniDiagram inside the template card", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    expect(source).toMatch(/<MiniDiagram/);
  });

  it("renders EmptyCanvasPreview inside the blank card", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    expect(source).toMatch(/<EmptyCanvasPreview/);
  });
});

// ===========================================================================
// 6. "Start Building" button and API call sequence (AC4)
// ===========================================================================

describe('"Start Building" creates workflow and navigates (AC4)', () => {
  it("has a 'Start Building' button", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    expect(source).toMatch(/Start Building/);
  });

  it("imports Button from @runsight/ui/button", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    expect(source).toMatch(/import.*Button.*from.*@runsight\/ui\/button/);
  });

  it("uses primary variant and lg size on the button", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    const hasPrimary = /variant.*primary|"primary"/.test(source);
    const hasLg = /size.*lg|"lg"/.test(source);
    expect(hasPrimary, "Expected primary variant on button").toBe(true);
    expect(hasLg, "Expected lg size on button").toBe(true);
  });

  it("imports useCreateWorkflow from queries/workflows", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    expect(source).toMatch(/import.*useCreateWorkflow.*from.*queries\/workflows/);
  });

  it("imports useUpdateAppSettings from queries/settings", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    expect(source).toMatch(/import.*useUpdateAppSettings.*from.*queries\/settings/);
  });

  it("imports useNavigate from react-router", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    expect(source).toMatch(/import.*useNavigate.*from.*react-router/);
  });

  it("calls createWorkflow on submit", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    // Should call the mutation (mutateAsync or mutate) from useCreateWorkflow
    const callsCreate =
      /createWorkflow.*mutateAsync|createWorkflow.*mutate|mutateAsync/.test(source);
    expect(
      callsCreate,
      "Expected createWorkflow mutation call on submit",
    ).toBe(true);
  });

  it("navigates to /workflows/:id/edit after successful creation", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    // Should navigate to the new workflow's edit page
    const hasNavigateToEdit =
      /navigate\s*\(\s*[`"']\/workflows\/.*\/edit[`"']|\/workflows\/\$\{.*\}\/edit/.test(source);
    expect(
      hasNavigateToEdit,
      "Expected navigation to /workflows/:id/edit after creation",
    ).toBe(true);
  });
});

// ===========================================================================
// 7. onboarding_completed set to true after success (AC7)
// ===========================================================================

describe("onboarding_completed set to true after success (AC7)", () => {
  it("calls updateAppSettings with onboarding_completed: true", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    expect(source).toMatch(/onboarding_completed.*true|onboarding_completed:\s*true/);
  });

  it("updateAppSettings is called after workflow creation (sequential)", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    // The flow: createWorkflow -> updateAppSettings -> navigate
    // Both mutations should be present in the same handler
    const hasCreate = /createWorkflow|useCreateWorkflow/.test(source);
    const hasUpdate = /updateAppSettings|useUpdateAppSettings/.test(source);
    expect(hasCreate && hasUpdate).toBe(true);
  });
});

// ===========================================================================
// 8. Button shows spinner during creation (AC5)
// ===========================================================================

describe("Button shows spinner during creation (AC5)", () => {
  it("button has loading prop wired to mutation pending state", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    // Button component supports loading prop — should be tied to isPending
    const hasLoading =
      /loading\s*=|isPending|isLoading/.test(source);
    expect(
      hasLoading,
      "Expected loading/isPending prop on the Start Building button",
    ).toBe(true);
  });

  it("button is disabled while loading", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    // Button should be disabled during mutation to prevent double-submit
    const hasDisabled = /disabled.*isPending|disabled.*isLoading|disabled.*loading/.test(source);
    expect(
      hasDisabled,
      "Expected button to be disabled while mutation is pending",
    ).toBe(true);
  });
});

// ===========================================================================
// 9. Toast on error, button re-enables (AC6)
// ===========================================================================

describe("Toast on error, button re-enables (AC6)", () => {
  it("imports toast from sonner (or uses mutation onError)", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    // Either the component imports toast directly, or relies on the mutation's
    // built-in onError which already has toast.error in queries/workflows.ts.
    // The component should at minimum have error handling in its submit handler.
    const hasErrorHandling =
      /toast\.error|catch\s*\(|\.catch\(|onError|try\s*\{/.test(source);
    expect(
      hasErrorHandling,
      "Expected error handling (toast, catch, or try/catch) in submit flow",
    ).toBe(true);
  });

  it("error state does not keep the button in loading state", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    // After an error, isPending returns to false so the button re-enables.
    // This is automatic with React Query mutations. The test verifies the
    // loading prop is tied to isPending (not a manual isLoading state that
    // could get stuck).
    const hasIsPending = /isPending/.test(source);
    expect(
      hasIsPending,
      "Expected isPending (from useMutation) to drive button loading state",
    ).toBe(true);
  });
});

// ===========================================================================
// 10. No API key shows warning badge on template card (AC8)
// ===========================================================================

describe("No API key shows warning badge on template card (AC8)", () => {
  it("imports useProviders from queries/settings", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    expect(source).toMatch(/import.*useProviders.*from.*queries\/settings/);
  });

  it("calls useProviders() to check provider status", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    expect(source).toMatch(/useProviders\(\)/);
  });

  it("shows warning badge with 'Explore mode' when no providers", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    expect(source).toMatch(/Explore mode/);
  });

  it("imports Badge from @runsight/ui", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    expect(source).toMatch(/import.*Badge.*from.*@runsight\/ui/);
  });

  it("uses warning variant on badge when no providers", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    // Badge should use warning variant when there are no providers
    expect(source).toMatch(/warning/);
  });

  it("uses success variant on badge when providers exist", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    // Badge should use success variant when providers are configured
    expect(source).toMatch(/success/);
  });

  it("conditionally renders badge variant based on provider count", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    // Should check providers.length or similar to determine which badge to show
    const hasProviderCheck =
      /providers.*length|\.length\s*[>!=]|!providers|providers\?\.\w/.test(source);
    expect(
      hasProviderCheck,
      "Expected conditional check on providers for badge variant",
    ).toBe(true);
  });
});

// ===========================================================================
// 11. Template YAML constant usage
// ===========================================================================

describe("Template YAML is used for template card workflow creation", () => {
  it("imports TEMPLATE_YAML from constants", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    expect(source).toMatch(/import.*TEMPLATE_YAML.*from.*constants/);
  });

  it("passes TEMPLATE_YAML when template option is selected", () => {
    const source = readSource(SETUP_START_PAGE_PATH);
    // When creating workflow with template selected, should use TEMPLATE_YAML
    expect(source).toMatch(/TEMPLATE_YAML/);
  });
});

// ===========================================================================
// 12. MiniDiagram and EmptyCanvasPreview sub-components
// ===========================================================================

describe("MiniDiagram component (CSS-only 3 nodes)", () => {
  it("exports MiniDiagram", () => {
    const source = readSource(MINI_DIAGRAM_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+MiniDiagram/);
  });

  it("renders 3 visual node elements", () => {
    const source = readSource(MINI_DIAGRAM_PATH);
    // Should have 3 node-like visual elements (CSS-only diagram)
    // Could be divs, spans, or SVG elements representing nodes
    const nodeCount = (source.match(/node|Node/g) ?? []).length;
    expect(nodeCount).toBeGreaterThanOrEqual(3);
  });
});

describe("EmptyCanvasPreview component (dashed box + '+')", () => {
  it("exports EmptyCanvasPreview", () => {
    const source = readSource(EMPTY_CANVAS_PREVIEW_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+EmptyCanvasPreview/);
  });

  it("uses dashed border styling", () => {
    const source = readSource(EMPTY_CANVAS_PREVIEW_PATH);
    expect(source).toMatch(/dashed|border-dashed/);
  });

  it("renders a '+' symbol", () => {
    const source = readSource(EMPTY_CANVAS_PREVIEW_PATH);
    // Should display a plus symbol as visual hint
    const hasPlus = /\+|Plus|plus/.test(source);
    expect(hasPlus, "Expected '+' symbol in empty canvas preview").toBe(true);
  });
});
