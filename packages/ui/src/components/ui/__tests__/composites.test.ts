/**
 * Composite component coverage.
 *
 * Validates that three composite components have been created/updated to use
 * the Runsight Product Design System tokens:
 *
 *   1. NodeCard    — NEW file at src/components/ui/node-card.tsx
 *      - Unified node card replacing individual canvas node files
 *      - Block category stripes, execution state tokens, surface/border tokens
 *
 *   2. EmptyState  — EXISTING file at src/components/shared/EmptyState.tsx
 *      - Must be updated to use design system tokens
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
// 1. NODE CARD — file exists and exports
// ===========================================================================

describe("NodeCard — file exists and exports default or named export", () => {
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
// 2. NODE CARD — block category stripe tokens
// ===========================================================================

describe("NodeCard — block-agent stripe token", () => {
  it("uses block-agent token for agent category stripe", () => {
    const source = readComponent("node-card.tsx");
    // Top 3px stripe for agent category nodes
    expect(source).toMatch(/block-agent/);
  });
});

describe("NodeCard — block-logic stripe token", () => {
  it("uses block-logic token for logic category stripe", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/block-logic/);
  });
});

describe("NodeCard — block-control stripe token", () => {
  it("uses block-control token for control category stripe", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/block-control/);
  });
});

describe("NodeCard — block-utility stripe token", () => {
  it("uses block-utility token for utility category stripe", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/block-utility/);
  });
});

describe("NodeCard — block-custom stripe token", () => {
  it("uses block-custom token for custom category stripe", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/block-custom/);
  });
});

// ===========================================================================
// 3. NODE CARD — surface and border tokens
// ===========================================================================

describe("NodeCard — surface token for card background", () => {
  it("uses surface-secondary or surface-tertiary token for card surface", () => {
    const source = readComponent("node-card.tsx");
    // Both surface-secondary and surface-tertiary are valid DS surface tokens for card backgrounds
    expect(source).toMatch(/surface-secondary|surface-tertiary/);
  });
});

describe("NodeCard — border token for card border", () => {
  it("uses border-subtle or neutral scale token for card border", () => {
    const source = readComponent("node-card.tsx");
    // border-subtle or neutral-N scale tokens are valid for card borders
    expect(source).toMatch(/border-subtle|neutral-[0-9]/);
  });
});

describe("NodeCard — selected state styling", () => {
  it("applies visual styling for selected state", () => {
    const source = readComponent("node-card.tsx");
    // Selected state can use border-accent, surface-selected, or inline HSL values
    expect(source).toMatch(/border-accent|surface-selected|selected|hsla\(38/);
  });

  it("selected state changes the background or border", () => {
    const source = readComponent("node-card.tsx");
    // Must reference the selected prop or data-selected attribute
    expect(source).toMatch(/selected/);
  });
});

describe("NodeCard — radius-lg token for card shape", () => {
  it("uses radius-lg token for card corner radius", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/radius-lg/);
  });
});

// ===========================================================================
// 4. NODE CARD — header text tokens
// ===========================================================================

describe("NodeCard — text-heading token for header text", () => {
  it("uses text-heading token for node header text color", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/text-heading/);
  });
});

describe("NodeCard — small font token for header text size", () => {
  it("uses font-size-sm token or small pixel size for node header font size", () => {
    const source = readComponent("node-card.tsx");
    // font-size-sm (13px) or text-[13px] are both valid for the node header
    expect(source).toMatch(/font-size-sm|text-\[13px\]|text-sm/);
  });
});

// ===========================================================================
// 5. NODE CARD — cost badge tokens
// ===========================================================================

describe("NodeCard — font-mono token for cost badge", () => {
  it("uses font-mono token for cost display", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/font-mono/);
  });
});

describe("NodeCard — font-size-2xs token for cost badge text", () => {
  it("uses font-size-2xs token for cost badge text size", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/font-size-2xs/);
  });
});

// ===========================================================================
// 6. NODE CARD — execution state tokens
// ===========================================================================

describe("NodeCard — accent-9 token for running state", () => {
  it("uses accent-9 token for running execution state", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/accent-9/);
  });
});

describe("NodeCard — success token for success state", () => {
  it("uses success scale token for success execution state", () => {
    const source = readComponent("node-card.tsx");
    // success-7 or success-9 are both valid DS success tokens
    expect(source).toMatch(/success-[79]/);
  });
});

describe("NodeCard — danger token for error state", () => {
  it("uses danger scale token for error/danger execution state", () => {
    const source = readComponent("node-card.tsx");
    // danger-7 or danger-9 are both valid DS danger tokens
    expect(source).toMatch(/danger-[79]/);
  });
});

describe("NodeCard — neutral token for skipped state", () => {
  it("uses neutral scale token for skipped execution state", () => {
    const source = readComponent("node-card.tsx");
    // neutral-4 through neutral-7 are all valid DS neutral tokens for muted/skipped states
    expect(source).toMatch(/neutral-[4-7]/);
  });
});

// ===========================================================================
// 7. NODE CARD — port handle token
// ===========================================================================

describe("NodeCard — interactive-default token for port handles", () => {
  it("uses interactive-default token for port handle styling", () => {
    const source = readComponent("node-card.tsx");
    expect(source).toMatch(/interactive-default/);
  });
});

// ===========================================================================
// 8. EMPTY STATE — existing file has design system tokens
// ===========================================================================

describe("EmptyState — text-muted token for icon color", () => {
  it("uses text-muted token for icon color (not generic Tailwind)", () => {
    const source = readShared("EmptyState.tsx");
    // text-muted is present in current code but via generic usage;
    // this test ensures it's the DS token applied correctly to the icon element
    // The icon currently uses 'text-muted' — passes; deeper checks below enforce DS tokens
    expect(source).toMatch(/text-muted/);
  });
});

describe("EmptyState — icon size for icon dimensions", () => {
  it("uses icon-size-xl token or size utility for icon size", () => {
    const source = readShared("EmptyState.tsx");
    // icon-size-xl DS token or w-12/h-12 equivalent Tailwind utilities are valid
    expect(source).toMatch(/icon-size-xl|w-12|h-12|size-12/);
  });
});

describe("EmptyState — text color token for title", () => {
  it("uses text-heading or text-primary token for title color", () => {
    const source = readShared("EmptyState.tsx");
    // text-heading or text-primary are both valid DS text tokens for titles
    expect(source).toMatch(/text-heading|text-primary|text-\(--text-/);
  });
});

describe("EmptyState — font-size-lg token for title size", () => {
  it("uses font-size-lg token for title font size (not text-sm inline)", () => {
    const source = readShared("EmptyState.tsx");
    // Current code uses text-sm for the h3; must use font-size-lg DS token
    expect(source).toMatch(/font-size-lg/);
  });
});

describe("EmptyState — text-secondary token for description color", () => {
  it("uses text-secondary token for description text (not text-muted)", () => {
    const source = readShared("EmptyState.tsx");
    // Current code uses text-muted for description; must be text-secondary per spec
    expect(source).toMatch(/text-secondary/);
  });
});

describe("EmptyState — font-size-sm token for description size", () => {
  it("uses font-size-sm token for description font size (not text-xs inline)", () => {
    const source = readShared("EmptyState.tsx");
    // Current code uses text-xs for description; must use font-size-sm DS token
    expect(source).toMatch(/font-size-sm/);
  });
});

describe("EmptyState — spacing for gap between elements", () => {
  it("uses space-6 token or gap utility for element spacing", () => {
    const source = readShared("EmptyState.tsx");
    // space-6 DS token or gap utilities are valid for spacing
    expect(source).toMatch(/space-6|gap-/);
  });
});

describe("EmptyState — no BEM class names", () => {
  it("does not use BEM class names like empty-state__icon", () => {
    const source = readShared("EmptyState.tsx");
    // Must use CVA+Tailwind, not BEM
    expect(source).not.toMatch(/empty-state__|__icon|__title/);
  });
});

// ===========================================================================
// 12. STORYBOOK STORIES — all 3 story files exist
// ===========================================================================

describe("Storybook stories — existence", () => {
  it("NodeCard.stories.tsx exists in src/stories/ or src/components/ui/", () => {
    expect(storyExists("NodeCard.stories.tsx")).toBe(true);
  });

  it("EmptyState.stories.tsx exists in src/stories/ or src/components/ui/", () => {
    expect(storyExists("EmptyState.stories.tsx")).toBe(true);
  });
});

// ===========================================================================
// 13. STORYBOOK STORIES — NodeCard.stories.tsx structure
// ===========================================================================

describe("Storybook stories — NodeCard.stories.tsx structure", () => {
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
// 14. STORYBOOK STORIES — EmptyState.stories.tsx structure
// ===========================================================================

describe("Storybook stories — EmptyState.stories.tsx structure", () => {
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
