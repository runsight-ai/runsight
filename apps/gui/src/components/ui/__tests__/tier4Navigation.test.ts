/**
 * RED-TEAM tests for RUN-301: Tier 4 Navigation.
 *
 * Validates that Tabs and the ShellLayout sidebar have been updated to use
 * Runsight design system tokens, and that Breadcrumb and Pagination have been
 * created to match the design system component spec. Also validates that
 * Storybook story files exist for all 4 components.
 *
 * Tests read component source files as strings and verify:
 *   1. Existing: Tabs (tabs.tsx) — required DS tokens present
 *   2. Existing: Sidebar (ShellLayout.tsx) — DS tokens for nav, widths, icons
 *   3. New: Breadcrumb (breadcrumb.tsx) — file exists, exports, tokens
 *   4. New: Pagination (pagination.tsx) — file exists, exports, tokens
 *   5. All 4: story files exist with proper Storybook structure
 *
 * Expected failures (current state):
 *   - tabs.tsx: missing border-subtle (no border token on list),
 *     text-secondary (inactive tabs use text-primary/60 / dark:text-muted instead),
 *     text-heading (active tabs use text-primary instead),
 *     interactive-default (active indicator uses bg-foreground not interactive-default),
 *     density-nav-item-height (list uses h-8 hardcoded instead of DS token)
 *   - ShellLayout.tsx: missing surface-secondary on sidebar bg (uses bg-sidebar alias
 *     without direct token reference), surface-hover (uses bg-surface-elevated instead),
 *     sidebar-active-indicator (active uses bg-interactive/12 not sidebar-active-indicator),
 *     sidebar-width-collapsed / sidebar-width-expanded (uses hardcoded w-[240px] / w-[52px]),
 *     icon-size-md (uses size-[18px] hardcoded instead of DS token)
 *   - breadcrumb.tsx does not exist
 *   - pagination.tsx does not exist
 *   - No story files exist for Tabs, Sidebar, Breadcrumb, or Pagination
 */

import { describe, it, expect } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------

const UI_DIR = resolve(__dirname, "..");
const LAYOUTS_DIR = resolve(__dirname, "..", "..", "..", "routes", "layouts");
const STORIES_DIR = resolve(__dirname, "..", "..", "..", "stories");

function componentExists(filename: string): boolean {
  return existsSync(resolve(UI_DIR, filename));
}

function readComponent(filename: string): string {
  return readFileSync(resolve(UI_DIR, filename), "utf-8");
}

function readLayout(filename: string): string {
  return readFileSync(resolve(LAYOUTS_DIR, filename), "utf-8");
}

function storyExists(filename: string): boolean {
  return (
    existsSync(resolve(STORIES_DIR, filename)) ||
    existsSync(resolve(UI_DIR, filename))
  );
}

function readStory(filename: string): string {
  const storiesPath = resolve(STORIES_DIR, filename);
  if (existsSync(storiesPath)) {
    return readFileSync(storiesPath, "utf-8");
  }
  return readFileSync(resolve(UI_DIR, filename), "utf-8");
}

// ===========================================================================
// 1. TABS — border-subtle token on list (AC1)
// ===========================================================================

describe("Tabs — border-subtle token on list border (AC1)", () => {
  it("uses border-subtle token for the tabs list bottom border", () => {
    const source = readComponent("tabs.tsx");
    // Spec: tabs list border uses --border-subtle
    // Current state: no border-subtle token in tabs.tsx (uses bg-surface-tertiary for list)
    expect(source).toMatch(/border-subtle/);
  });
});

// ===========================================================================
// 2. TABS — text-secondary token for inactive tabs (AC1)
// ===========================================================================

describe("Tabs — text-secondary token for inactive tab text (AC1)", () => {
  it("uses text-secondary token for inactive tab text color", () => {
    const source = readComponent("tabs.tsx");
    // Spec: inactive tab text uses --text-secondary
    // Current state: uses text-primary/60 and dark:text-muted (no text-secondary token)
    expect(source).toMatch(/text-secondary/);
  });
});

// ===========================================================================
// 3. TABS — text-heading token for active tab (AC1)
// ===========================================================================

describe("Tabs — text-heading token for active tab text (AC1)", () => {
  it("uses text-heading token for active tab text color", () => {
    const source = readComponent("tabs.tsx");
    // Spec: active tab text uses --text-heading
    // Current state: data-active:text-primary (wrong token — text-primary not text-heading)
    expect(source).toMatch(/text-heading/);
  });
});

// ===========================================================================
// 4. TABS — interactive-default token for active underline (AC1)
// ===========================================================================

describe("Tabs — interactive-default token for active tab underline (AC1)", () => {
  it("uses interactive-default token for the active tab 2px underline indicator", () => {
    const source = readComponent("tabs.tsx");
    // Spec: active underline uses --interactive-default
    // Current state: after:bg-foreground (not interactive-default)
    expect(source).toMatch(/interactive-default/);
  });
});

// ===========================================================================
// 5. TABS — font-size-sm token (AC1)
// ===========================================================================

describe("Tabs — font-size-sm or text-sm token for tab font size (AC1)", () => {
  it("uses font-size-sm or text-sm design system class for tab font size", () => {
    const source = readComponent("tabs.tsx");
    // Spec: tabs font size uses --font-size-sm; text-sm maps to this token in Tailwind
    expect(source).toMatch(/font-size-sm|text-sm/);
  });
});

// ===========================================================================
// 6. TABS — font-medium token (AC1)
// ===========================================================================

describe("Tabs — font-medium or font-weight-medium token for tab weight (AC1)", () => {
  it("uses font-medium or font-weight-medium for tab font weight", () => {
    const source = readComponent("tabs.tsx");
    // Spec: tabs font weight uses --font-weight-medium
    expect(source).toMatch(/font-medium|font-weight-medium/);
  });
});

// ===========================================================================
// 7. TABS — density-nav-item-height token (AC1)
// ===========================================================================

describe("Tabs — density-nav-item-height token for tab height (AC1)", () => {
  it("uses density-nav-item-height token for tabs list height", () => {
    const source = readComponent("tabs.tsx");
    // Spec: tab height uses --density-nav-item-height DS token
    // Current state: group-data-horizontal/tabs:h-8 (hardcoded h-8, no density token)
    expect(source).toMatch(/density-nav-item-height/);
  });
});

// ===========================================================================
// 8. SIDEBAR — sidebar-bg token reference on aside (AC2)
// ===========================================================================

describe("Sidebar — sidebar-bg CSS variable reference on the sidebar aside (AC2)", () => {
  it("uses sidebar-bg CSS variable (var(--sidebar-bg)) on the sidebar aside element", () => {
    const source = readLayout("ShellLayout.tsx");
    // Spec: sidebar background must use var(--sidebar-bg) or var(--surface-secondary)
    // Current state: uses Tailwind utility class bg-sidebar (shorthand), not an explicit
    //   var(--sidebar-bg) reference. The token must be referenced explicitly.
    expect(source).toMatch(/var\(--sidebar-bg\)|var\(--surface-secondary\)/);
  });
});

// ===========================================================================
// 9. SIDEBAR — surface-hover or sidebar-hover token for nav item hover (AC2)
// ===========================================================================

describe("Sidebar — surface-hover or sidebar-hover token for nav item hover (AC2)", () => {
  it("uses surface-hover or sidebar-hover token for nav item hover state", () => {
    const source = readLayout("ShellLayout.tsx");
    // Spec: nav item hover uses --surface-hover or --sidebar-hover
    // Current state: hover:bg-surface-elevated (wrong token — not surface-hover/sidebar-hover)
    expect(source).toMatch(/surface-hover|sidebar-hover/);
  });
});

// ===========================================================================
// 10. SIDEBAR — sidebar-active-indicator token for active nav item (AC2)
// ===========================================================================

describe("Sidebar — sidebar-active-indicator token for active nav item (AC2)", () => {
  it("uses sidebar-active-indicator token (not bg-interactive/12 opacity shorthand) for active nav", () => {
    const source = readLayout("ShellLayout.tsx");
    // Spec: active nav item background uses --sidebar-active-indicator DS token
    // Current state: bg-interactive/12 (Tailwind opacity modifier shorthand, not the DS token)
    // The sidebar-active-indicator token must be referenced explicitly, not via bg-interactive/12
    expect(source).toMatch(/sidebar-active-indicator/);
  });
});

// ===========================================================================
// 11. SIDEBAR — sidebar-width-collapsed token (AC2)
// ===========================================================================

describe("Sidebar — sidebar-width-collapsed token for collapsed width (AC2)", () => {
  it("uses sidebar-width-collapsed token for collapsed sidebar width", () => {
    const source = readLayout("ShellLayout.tsx");
    // Spec: collapsed sidebar width uses --sidebar-width-collapsed (48px)
    // Current state: w-[52px] (hardcoded, wrong value — spec is 48px via token)
    expect(source).toMatch(/sidebar-width-collapsed/);
  });
});

// ===========================================================================
// 12. SIDEBAR — sidebar-width-expanded token (AC2)
// ===========================================================================

describe("Sidebar — sidebar-width-expanded token for expanded width (AC2)", () => {
  it("uses sidebar-width-expanded token for expanded sidebar width", () => {
    const source = readLayout("ShellLayout.tsx");
    // Spec: expanded sidebar width uses --sidebar-width-expanded (240px)
    // Current state: w-[240px] (hardcoded px value, not the DS token)
    expect(source).toMatch(/sidebar-width-expanded/);
  });
});

// ===========================================================================
// 13. SIDEBAR — icon-size-md token for nav icons (AC2)
// ===========================================================================

describe("Sidebar — icon-size-md token for nav icon size (AC2)", () => {
  it("uses icon-size-md token for sidebar nav icon sizing", () => {
    const source = readLayout("ShellLayout.tsx");
    // Spec: nav icons use --icon-size-md
    // Current state: size-[18px] (hardcoded pixel value, not the DS token)
    expect(source).toMatch(/icon-size-md/);
  });
});

// ===========================================================================
// 14. BREADCRUMB — file exists (AC3)
// ===========================================================================

describe("Breadcrumb — component file exists (AC3)", () => {
  it("breadcrumb.tsx exists in src/components/ui/", () => {
    expect(componentExists("breadcrumb.tsx")).toBe(true);
  });
});

// ===========================================================================
// 15. BREADCRUMB — named exports (AC3)
// ===========================================================================

describe("Breadcrumb — named exports (AC3)", () => {
  it("exports a Breadcrumb component", () => {
    const source = readComponent("breadcrumb.tsx");
    expect(source).toMatch(/export.*\bBreadcrumb\b/);
  });

  it("exports a BreadcrumbItem component or equivalent", () => {
    const source = readComponent("breadcrumb.tsx");
    // Spec: BreadcrumbItem (or BreadcrumbLink / BreadcrumbPage sub-components)
    expect(source).toMatch(/export.*\bBreadcrumbItem\b|export.*\bBreadcrumbLink\b|export.*\bBreadcrumbPage\b/);
  });
});

// ===========================================================================
// 16. BREADCRUMB — design system tokens (AC3)
// ===========================================================================

describe("Breadcrumb — design system tokens (AC3)", () => {
  it("uses text-muted token for separator color", () => {
    const source = readComponent("breadcrumb.tsx");
    // Spec: separator color uses --text-muted
    expect(source).toMatch(/text-muted/);
  });

  it("uses text-heading token for the current (active) breadcrumb item", () => {
    const source = readComponent("breadcrumb.tsx");
    // Spec: current item text color uses --text-heading
    expect(source).toMatch(/text-heading/);
  });

  it("uses text-secondary token for previous (ancestor) breadcrumb items", () => {
    const source = readComponent("breadcrumb.tsx");
    // Spec: previous items text color uses --text-secondary
    expect(source).toMatch(/text-secondary/);
  });

  it("uses text-primary token for breadcrumb item hover state", () => {
    const source = readComponent("breadcrumb.tsx");
    // Spec: previous items hover state uses --text-primary
    expect(source).toMatch(/text-primary/);
  });

  it("uses font-size-sm or text-sm token for breadcrumb font size", () => {
    const source = readComponent("breadcrumb.tsx");
    // Spec: breadcrumb font size uses --font-size-sm
    expect(source).toMatch(/font-size-sm|text-sm/);
  });
});

// ===========================================================================
// 17. BREADCRUMB — separator element (AC3)
// ===========================================================================

describe("Breadcrumb — separator element (AC3)", () => {
  it("renders a separator between breadcrumb items", () => {
    const source = readComponent("breadcrumb.tsx");
    // Spec: visual separator between items (slash, chevron, or similar)
    expect(source).toMatch(/separator|Separator|chevron|Chevron|slash|\/>/i);
  });
});

// ===========================================================================
// 18. PAGINATION — file exists (AC4)
// ===========================================================================

describe("Pagination — component file exists (AC4)", () => {
  it("pagination.tsx exists in src/components/ui/", () => {
    expect(componentExists("pagination.tsx")).toBe(true);
  });
});

// ===========================================================================
// 19. PAGINATION — named export (AC4)
// ===========================================================================

describe("Pagination — named export (AC4)", () => {
  it("exports a Pagination component", () => {
    const source = readComponent("pagination.tsx");
    expect(source).toMatch(/export.*\bPagination\b/);
  });
});

// ===========================================================================
// 20. PAGINATION — design system tokens (AC4)
// ===========================================================================

describe("Pagination — design system tokens (AC4)", () => {
  it("uses interactive-default token for active page background", () => {
    const source = readComponent("pagination.tsx");
    // Spec: active page button background uses --interactive-default
    expect(source).toMatch(/interactive-default/);
  });

  it("uses text-secondary or text-muted token for range display text", () => {
    const source = readComponent("pagination.tsx");
    // Spec: range display (e.g. "1-10 of 100") uses --text-secondary or --text-muted
    expect(source).toMatch(/text-secondary|text-muted/);
  });
});

// ===========================================================================
// 21. PAGINATION — ghost buttons for page navigation (AC4)
// ===========================================================================

describe("Pagination — ghost variant page buttons (AC4)", () => {
  it("uses ghost button variant for page number buttons", () => {
    const source = readComponent("pagination.tsx");
    // Spec: page buttons are ghost style (no filled background when inactive)
    expect(source).toMatch(/ghost|variant.*ghost|Ghost/);
  });
});

// ===========================================================================
// 22. PAGINATION — range display with "of" pattern (AC4)
// ===========================================================================

describe("Pagination — range display with 'of' pattern (AC4)", () => {
  it("supports a range display pattern like '1-10 of 100'", () => {
    const source = readComponent("pagination.tsx");
    // Spec: shows range e.g. "1-10 of 100" — check for "of" keyword in context
    expect(source).toMatch(/\bof\b|total|count/i);
  });
});

// ===========================================================================
// 23. STORYBOOK STORIES — all 4 navigation story files exist (AC5)
// ===========================================================================

describe("Storybook stories — existence (AC5)", () => {
  it("Tabs.stories.tsx exists in src/stories/ or src/components/ui/", () => {
    expect(storyExists("Tabs.stories.tsx")).toBe(true);
  });

  it("Sidebar.stories.tsx exists in src/stories/ or src/components/ui/", () => {
    expect(storyExists("Sidebar.stories.tsx")).toBe(true);
  });

  it("Breadcrumb.stories.tsx exists in src/stories/ or src/components/ui/", () => {
    expect(storyExists("Breadcrumb.stories.tsx")).toBe(true);
  });

  it("Pagination.stories.tsx exists in src/stories/ or src/components/ui/", () => {
    expect(storyExists("Pagination.stories.tsx")).toBe(true);
  });
});

// ===========================================================================
// 24. STORYBOOK STORIES — Tabs.stories.tsx structure (AC5)
// ===========================================================================

describe("Storybook stories — Tabs.stories.tsx structure (AC5)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("Tabs.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("Tabs.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("Tabs.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });

  it("covers basic/default usage", () => {
    const content = readStory("Tabs.stories.tsx");
    expect(content).toMatch(/Default|Basic|Primary/i);
  });

  it("covers the line variant (underline indicator)", () => {
    const content = readStory("Tabs.stories.tsx");
    expect(content).toMatch(/line|Line|underline|Underline/i);
  });
});

// ===========================================================================
// 25. STORYBOOK STORIES — Sidebar.stories.tsx structure (AC5)
// ===========================================================================

describe("Storybook stories — Sidebar.stories.tsx structure (AC5)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("Sidebar.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("Sidebar.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("Sidebar.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });

  it("covers expanded sidebar state", () => {
    const content = readStory("Sidebar.stories.tsx");
    expect(content).toMatch(/Expanded|expanded|Open|open/i);
  });

  it("covers collapsed sidebar state", () => {
    const content = readStory("Sidebar.stories.tsx");
    expect(content).toMatch(/Collapsed|collapsed|Closed|closed/i);
  });
});

// ===========================================================================
// 26. STORYBOOK STORIES — Breadcrumb.stories.tsx structure (AC5)
// ===========================================================================

describe("Storybook stories — Breadcrumb.stories.tsx structure (AC5)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("Breadcrumb.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("Breadcrumb.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("Breadcrumb.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });

  it("covers basic/default usage", () => {
    const content = readStory("Breadcrumb.stories.tsx");
    expect(content).toMatch(/Default|Basic|Primary/i);
  });

  it("covers multi-level breadcrumb path", () => {
    const content = readStory("Breadcrumb.stories.tsx");
    expect(content).toMatch(/multi|Multi|level|Level|nested|Nested|deep|Deep/i);
  });
});

// ===========================================================================
// 27. STORYBOOK STORIES — Pagination.stories.tsx structure (AC5)
// ===========================================================================

describe("Storybook stories — Pagination.stories.tsx structure (AC5)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("Pagination.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("Pagination.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("Pagination.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });

  it("covers basic/default usage", () => {
    const content = readStory("Pagination.stories.tsx");
    expect(content).toMatch(/Default|Basic|Primary/i);
  });

  it("covers range display (of pattern)", () => {
    const content = readStory("Pagination.stories.tsx");
    expect(content).toMatch(/range|Range|of\s+\d|total|Total|count|Count/i);
  });
});
