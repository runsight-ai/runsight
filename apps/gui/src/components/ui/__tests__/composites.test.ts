/**
 * RED-TEAM tests for RUN-303: Composite Components.
 *
 * Validates that three composite components have been created/updated to use
 * the Runsight Product Design System tokens:
 *
 *   1. NodeCard    — NEW file at src/components/ui/node-card.tsx
 *      - Unified node card replacing individual canvas node files
 *      - Block category stripes, execution state tokens, surface/border tokens
 *
 *   2. AppShell    — NEW file at src/components/ui/app-shell.tsx
 *      - CSS Grid layout shell with panel size tokens
 *
 *   3. EmptyState  — EXISTING file at src/components/shared/EmptyState.tsx
 *      - Must be updated to use design system tokens
 *
 * Expected failures (current state):
 *   - node-card.tsx does not exist
 *   - app-shell.tsx does not exist
 *   - EmptyState.tsx uses generic Tailwind classes (gap-3, p-8, h-12, w-12,
 *     rounded-lg, text-sm, font-medium, text-xs) instead of design system
 *     tokens (space-6, icon-size-xl, text-heading, font-size-lg, text-secondary,
 *     font-size-sm, text-muted)
 *   - No story files exist for NodeCard, AppShell, or EmptyState
 */

import { describe, it, expect } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------

const UI_DIR = resolve(__dirname, "..");
const SHARED_DIR = resolve(__dirname, "..", "..", "shared");
const STORIES_DIR = resolve(__dirname, "..", "..", "..", "stories");

function componentExists(filename: string): boolean {
  return existsSync(resolve(UI_DIR, filename));
}

function readComponent(filename: string): string {
  return readFileSync(resolve(UI_DIR, filename), "utf-8");
}

function sharedExists(filename: string): boolean {
  return existsSync(resolve(SHARED_DIR, filename));
}

function readShared(filename: string): string {
  return readFileSync(resolve(SHARED_DIR, filename), "utf-8");
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
// 1. NODE CARD — file exists and exports (AC1)
// ===========================================================================

describe("NodeCard — file exists and exports default or named export (AC1)", () => {
  it("node-card.tsx exists in src/components/ui/", () => {
    expect(componentExists("node-card.tsx")).toBe(true);
  });

  it("node-card.tsx exports NodeCard", () => {
    const source = readComponent("node-card.tsx");
    // Must export a NodeCard component (named or default)
    expect(source).toMatch(/export.*NodeCard/);
  });

  it("node-card.tsx is non-empty", () => {
    const source = readComponent("node-card.tsx");
    expect(source.length).toBeGreaterThan(0);
  });
});

// ===========================================================================
// 2. NODE CARD — block category stripe tokens (AC1)
// ===========================================================================

describe("NodeCard — block-agent stripe token (AC1)", () => {
  it("uses block-agent token for agent category stripe", () => {
    const source = readComponent("node-card.tsx");
    // Top 3px stripe for agent category nodes
    expect(source).toMatch(/block-agent/);
  });
});

describe("NodeCard — block-logic stripe token (AC1)", () => {
  it("uses block-logic token for logic category stripe", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/block-logic/);
  });
});

describe("NodeCard — block-control stripe token (AC1)", () => {
  it("uses block-control token for control category stripe", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/block-control/);
  });
});

describe("NodeCard — block-utility stripe token (AC1)", () => {
  it("uses block-utility token for utility category stripe", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/block-utility/);
  });
});

describe("NodeCard — block-custom stripe token (AC1)", () => {
  it("uses block-custom token for custom category stripe", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/block-custom/);
  });
});

// ===========================================================================
// 3. NODE CARD — surface and border tokens (AC1)
// ===========================================================================

describe("NodeCard — surface-secondary token for card background (AC1)", () => {
  it("uses surface-secondary token for card surface", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/surface-secondary/);
  });
});

describe("NodeCard — border-subtle token for card border (AC1)", () => {
  it("uses border-subtle token for card border", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/border-subtle/);
  });
});

describe("NodeCard — border-accent and surface-selected for selected state (AC1)", () => {
  it("uses border-accent token for selected state border", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/border-accent/);
  });

  it("uses surface-selected token for selected state background", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/surface-selected/);
  });
});

describe("NodeCard — radius-lg token for card shape (AC1)", () => {
  it("uses radius-lg token for card corner radius", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/radius-lg/);
  });
});

// ===========================================================================
// 4. NODE CARD — header text tokens (AC1)
// ===========================================================================

describe("NodeCard — text-heading token for header text (AC1)", () => {
  it("uses text-heading token for node header text color", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/text-heading/);
  });
});

describe("NodeCard — font-size-sm token for header text size (AC1)", () => {
  it("uses font-size-sm token for node header font size", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/font-size-sm/);
  });
});

// ===========================================================================
// 5. NODE CARD — cost badge tokens (AC1)
// ===========================================================================

describe("NodeCard — font-mono token for cost badge (AC1)", () => {
  it("uses font-mono token for cost display", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/font-mono/);
  });
});

describe("NodeCard — font-size-2xs token for cost badge text (AC1)", () => {
  it("uses font-size-2xs token for cost badge text size", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/font-size-2xs/);
  });
});

// ===========================================================================
// 6. NODE CARD — execution state tokens (AC1)
// ===========================================================================

describe("NodeCard — accent-9 token for running state (AC1)", () => {
  it("uses accent-9 token for running execution state", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/accent-9/);
  });
});

describe("NodeCard — success-7 token for success state (AC1)", () => {
  it("uses success-7 token for success execution state", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/success-7/);
  });
});

describe("NodeCard — danger-7 token for error state (AC1)", () => {
  it("uses danger-7 token for error/danger execution state", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/danger-7/);
  });
});

describe("NodeCard — neutral-6 token for skipped state (AC1)", () => {
  it("uses neutral-6 token for skipped execution state", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/neutral-6/);
  });
});

// ===========================================================================
// 7. NODE CARD — port handle token (AC1)
// ===========================================================================

describe("NodeCard — interactive-default token for port handles (AC1)", () => {
  it("uses interactive-default token for port handle styling", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/interactive-default/);
  });
});

// ===========================================================================
// 8. APP SHELL — file exists and exports (AC2)
// ===========================================================================

describe("AppShell — file exists and exports default or named export (AC2)", () => {
  it("app-shell.tsx exists in src/components/ui/", () => {
    expect(componentExists("app-shell.tsx")).toBe(true);
  });

  it("app-shell.tsx exports AppShell", () => {
    const source = readComponent("app-shell.tsx");
    expect(source).toMatch(/export.*AppShell/);
  });

  it("app-shell.tsx is non-empty", () => {
    const source = readComponent("app-shell.tsx");
    expect(source.length).toBeGreaterThan(0);
  });
});

// ===========================================================================
// 9. APP SHELL — CSS Grid layout (AC2)
// ===========================================================================

describe("AppShell — CSS Grid layout (AC2)", () => {
  it("uses CSS grid layout (grid or display: grid)", () => {
    const source = readComponent("app-shell.tsx");
    // Must use a grid class or inline grid style
    expect(source).toMatch(/\bgrid\b|display.*grid/);
  });
});

// ===========================================================================
// 10. APP SHELL — panel size tokens (AC2)
// ===========================================================================

describe("AppShell — header-height token (AC2)", () => {
  it("uses header-height token (40px) for header area", () => {
    const source = readComponent("app-shell.tsx");
    expect(source).toMatch(/header-height/);
  });
});

describe("AppShell — status-bar-height token (AC2)", () => {
  it("uses status-bar-height token (22px) for status bar area", () => {
    const source = readComponent("app-shell.tsx");
    expect(source).toMatch(/status-bar-height/);
  });
});

describe("AppShell — sidebar-width-collapsed token (AC2)", () => {
  it("uses sidebar-width-collapsed token (48px) for collapsed sidebar", () => {
    const source = readComponent("app-shell.tsx");
    expect(source).toMatch(/sidebar-width-collapsed/);
  });
});

describe("AppShell — sidebar-width-expanded token (AC2)", () => {
  it("uses sidebar-width-expanded token (240px) for expanded sidebar", () => {
    const source = readComponent("app-shell.tsx");
    expect(source).toMatch(/sidebar-width-expanded/);
  });
});

describe("AppShell — inspector-width token (AC2)", () => {
  it("uses inspector-width token (320px) for inspector panel", () => {
    const source = readComponent("app-shell.tsx");
    expect(source).toMatch(/inspector-width(?!-min)(?!-max)/);
  });
});

describe("AppShell — inspector-width-min token (AC2)", () => {
  it("uses inspector-width-min token (240px) for inspector panel min width", () => {
    const source = readComponent("app-shell.tsx");
    expect(source).toMatch(/inspector-width-min/);
  });
});

describe("AppShell — inspector-width-max token (AC2)", () => {
  it("uses inspector-width-max token (480px) for inspector panel max width", () => {
    const source = readComponent("app-shell.tsx");
    expect(source).toMatch(/inspector-width-max/);
  });
});

// ===========================================================================
// 11. EMPTY STATE — existing file has design system tokens (AC3)
// ===========================================================================

describe("EmptyState — text-muted token for icon color (AC3)", () => {
  it("uses text-muted token for icon color (not generic Tailwind)", () => {
    const source = readShared("EmptyState.tsx");
    // text-muted is present in current code but via generic usage;
    // this test ensures it's the DS token applied correctly to the icon element
    // The icon currently uses 'text-muted' — passes; deeper checks below enforce DS tokens
    expect(source).toMatch(/text-muted/);
  });
});

describe("EmptyState — icon-size-xl token for icon dimensions (AC3)", () => {
  it("uses icon-size-xl token for icon size (not h-6 w-6 inline)", () => {
    const source = readShared("EmptyState.tsx");
    // Current code uses h-6 w-6 (inline Tailwind); must use icon-size-xl DS token
    expect(source).toMatch(/icon-size-xl/);
  });
});

describe("EmptyState — text-heading token for title color (AC3)", () => {
  it("uses text-heading token for title (not generic text-primary)", () => {
    const source = readShared("EmptyState.tsx");
    // Current code uses text-primary on the h3; must use text-heading
    expect(source).toMatch(/text-heading/);
  });
});

describe("EmptyState — font-size-lg token for title size (AC3)", () => {
  it("uses font-size-lg token for title font size (not text-sm inline)", () => {
    const source = readShared("EmptyState.tsx");
    // Current code uses text-sm for the h3; must use font-size-lg DS token
    expect(source).toMatch(/font-size-lg/);
  });
});

describe("EmptyState — text-secondary token for description color (AC3)", () => {
  it("uses text-secondary token for description text (not text-muted)", () => {
    const source = readShared("EmptyState.tsx");
    // Current code uses text-muted for description; must be text-secondary per spec
    expect(source).toMatch(/text-secondary/);
  });
});

describe("EmptyState — font-size-sm token for description size (AC3)", () => {
  it("uses font-size-sm token for description font size (not text-xs inline)", () => {
    const source = readShared("EmptyState.tsx");
    // Current code uses text-xs for description; must use font-size-sm DS token
    expect(source).toMatch(/font-size-sm/);
  });
});

describe("EmptyState — space-6 token for gap spacing (AC3)", () => {
  it("uses space-6 token for gap between elements (not gap-3 or p-8 inline)", () => {
    const source = readShared("EmptyState.tsx");
    // Current code uses gap-3 and p-8; must use space-6 DS token
    expect(source).toMatch(/space-6/);
  });
});

describe("EmptyState — no generic inline Tailwind size classes (AC3)", () => {
  it("does not use h-6 w-6 for icon (replaced by icon-size-xl)", () => {
    const source = readShared("EmptyState.tsx");
    // Old: h-6 w-6 on the icon element — must be replaced with icon-size-xl
    expect(source).not.toMatch(/\bh-6\b.*\bw-6\b|\bw-6\b.*\bh-6\b/);
  });

  it("does not use h-12 w-12 for icon container (replaced by icon-size-xl token)", () => {
    const source = readShared("EmptyState.tsx");
    expect(source).not.toMatch(/\bh-12\b.*\bw-12\b|\bw-12\b.*\bh-12\b/);
  });

  it("does not use gap-3 for element spacing (replaced by space-6)", () => {
    const source = readShared("EmptyState.tsx");
    expect(source).not.toMatch(/\bgap-3\b/);
  });

  it("does not use p-8 for container padding (replaced by space-6)", () => {
    const source = readShared("EmptyState.tsx");
    expect(source).not.toMatch(/\bp-8\b/);
  });

  it("does not use text-sm on title (replaced by font-size-lg)", () => {
    const source = readShared("EmptyState.tsx");
    // text-sm on the h3 title element — must be replaced with font-size-lg
    expect(source).not.toMatch(/\btext-sm\b/);
  });

  it("does not use text-xs on description (replaced by font-size-sm)", () => {
    const source = readShared("EmptyState.tsx");
    // text-xs on the description paragraph — must be replaced with font-size-sm
    expect(source).not.toMatch(/\btext-xs\b/);
  });
});

// ===========================================================================
// 12. STORYBOOK STORIES — all 3 story files exist (AC4)
// ===========================================================================

describe("Storybook stories — existence (AC4)", () => {
  it("NodeCard.stories.tsx exists in src/stories/ or src/components/ui/", () => {
    expect(storyExists("NodeCard.stories.tsx")).toBe(true);
  });

  it("AppShell.stories.tsx exists in src/stories/ or src/components/ui/", () => {
    expect(storyExists("AppShell.stories.tsx")).toBe(true);
  });

  it("EmptyState.stories.tsx exists in src/stories/ or src/components/ui/", () => {
    expect(storyExists("EmptyState.stories.tsx")).toBe(true);
  });
});

// ===========================================================================
// 13. STORYBOOK STORIES — NodeCard.stories.tsx structure (AC4)
// ===========================================================================

describe("Storybook stories — NodeCard.stories.tsx structure (AC4)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("NodeCard.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("NodeCard.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("NodeCard.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });

  it("covers block category variants (agent, logic, control, utility, custom)", () => {
    const content = readStory("NodeCard.stories.tsx");
    expect(content).toMatch(/agent|logic|control|utility|custom/i);
  });

  it("covers execution states (running, success, error/danger, skipped)", () => {
    const content = readStory("NodeCard.stories.tsx");
    expect(content).toMatch(/running|success|error|danger|skipped/i);
  });

  it("covers selected state", () => {
    const content = readStory("NodeCard.stories.tsx");
    expect(content).toMatch(/selected/i);
  });
});

// ===========================================================================
// 14. STORYBOOK STORIES — AppShell.stories.tsx structure (AC4)
// ===========================================================================

describe("Storybook stories — AppShell.stories.tsx structure (AC4)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("AppShell.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("AppShell.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("AppShell.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });

  it("covers collapsed sidebar state", () => {
    const content = readStory("AppShell.stories.tsx");
    expect(content).toMatch(/collapsed/i);
  });

  it("covers expanded sidebar state", () => {
    const content = readStory("AppShell.stories.tsx");
    expect(content).toMatch(/expanded/i);
  });

  it("covers inspector panel visibility", () => {
    const content = readStory("AppShell.stories.tsx");
    expect(content).toMatch(/inspector/i);
  });
});

// ===========================================================================
// 15. STORYBOOK STORIES — EmptyState.stories.tsx structure (AC4)
// ===========================================================================

describe("Storybook stories — EmptyState.stories.tsx structure (AC4)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("EmptyState.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("EmptyState.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("EmptyState.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });

  it("covers story with action button", () => {
    const content = readStory("EmptyState.stories.tsx");
    expect(content).toMatch(/action/i);
  });

  it("covers story without description (title-only)", () => {
    const content = readStory("EmptyState.stories.tsx");
    // Should have a story variant showing the no-description case
    expect(content).toMatch(/WithoutDescription|NoDescription|TitleOnly|without.*description|no.*description/i);
  });
});
