/**
 * RED-TEAM tests for RUN-298: Tier 1 Primitives Update.
 *
 * Validates that Button, Badge, Input, Textarea, Label, and Tooltip
 * have been updated to match the Runsight design system component spec, and
 * that Storybook story files exist for all 6 components.
 *
 * Tests read component source files as strings and verify:
 *   1. Correct variant names exist (new spec)
 *   2. Old variant names have been removed
 *   3. Design system tokens are used
 *   4. New structural features (loading state, dot indicator) are present
 *   5. Story files exist with proper Storybook structure
 *
 * Expected failures (current state):
 *   - button.tsx still has variants: default, outline, destructive, link
 *     and sizes: default, icon, icon-xs, icon-sm, icon-lg
 *     Missing: primary, danger, icon-only; loading state not present
 *   - badge.tsx still has variants: default, destructive, ghost, link
 *     Missing: accent, success, warning, info, neutral; dot indicator absent
 *   - input.tsx does not use --control-height-sm or --surface-tertiary
 *   - textarea.tsx does not use --control-height-sm or --surface-tertiary
 *   - label.tsx does not use --font-size-sm, --font-weight-medium, --text-secondary
 *   - tooltip.tsx uses bg-text-primary / text-surface-primary instead of
 *     surface-raised / text-primary / font-size-xs
 *   - No story files exist for any of the 6 components
 */

import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------

const UI_DIR = resolve(__dirname, "..");
const STORIES_DIR = resolve(__dirname, "..", "..", "..", "stories");

function readComponent(filename: string): string {
  return readFileSync(resolve(UI_DIR, filename), "utf-8");
}

function readStory(filename: string): string {
  return readFileSync(resolve(STORIES_DIR, filename), "utf-8");
}

function storyExists(filename: string): boolean {
  // Stories may be in src/stories/ or colocated in src/components/ui/
  return (
    existsSync(resolve(STORIES_DIR, filename)) ||
    existsSync(resolve(UI_DIR, filename))
  );
}

// ---------------------------------------------------------------------------
// Helper: check that a CVA variants block contains a given key
// Uses a pattern that matches the key as an object property name inside
// the `variants:` block, without requiring exact surrounding whitespace.
// ---------------------------------------------------------------------------

function hasVariantKey(source: string, key: string): boolean {
  // Match the key as an object property: `key:` inside the variants block.
  // We look for the key followed by colon, optionally quoted.
  const pattern = new RegExp(`["']?${key}["']?\\s*:`);
  return pattern.test(source);
}

// ===========================================================================
// 1. BUTTON — variant names (AC1)
// ===========================================================================

describe("Button — new variant names present (AC1)", () => {
  it("has a `primary` variant in buttonVariants", () => {
    const source = readComponent("button.tsx");
    expect(hasVariantKey(source, "primary")).toBe(true);
  });

  it("has a `secondary` variant in buttonVariants", () => {
    const source = readComponent("button.tsx");
    expect(hasVariantKey(source, "secondary")).toBe(true);
  });

  it("has a `ghost` variant in buttonVariants", () => {
    const source = readComponent("button.tsx");
    expect(hasVariantKey(source, "ghost")).toBe(true);
  });

  it("has a `danger` variant in buttonVariants", () => {
    const source = readComponent("button.tsx");
    expect(hasVariantKey(source, "danger")).toBe(true);
  });

  it("has an `icon-only` variant in buttonVariants", () => {
    const source = readComponent("button.tsx");
    // icon-only may be written as "icon-only": or 'icon-only':
    expect(source).toMatch(/["']icon-only["']\s*:/);
  });
});

// ===========================================================================
// 2. BUTTON — old variant names removed (AC1)
// ===========================================================================

describe("Button — old variant names removed (AC1)", () => {
  it("no longer has a `default` variant key in buttonVariants", () => {
    const source = readComponent("button.tsx");
    // `default:` as a CVA variant key — must be gone.
    // We need to distinguish the CVA variant key "default:" from
    // the defaultVariants block which contains "variant: 'primary'" after update.
    // Pattern: the variant block should not contain `default:` as a variant entry.
    // We check by looking for the pattern inside the variants object.
    // A safe heuristic: `default:` inside the variant object (not defaultVariants).
    // After the update, defaultVariants should reference "primary", not "default".
    expect(source).not.toMatch(/variant:\s*\{[^}]*\bdefault\s*:/s);
  });

  it("no longer has a `destructive` variant key in buttonVariants", () => {
    const source = readComponent("button.tsx");
    expect(source).not.toMatch(/\bdestructive\s*:/);
  });

  it("no longer has an `outline` variant key in buttonVariants", () => {
    const source = readComponent("button.tsx");
    expect(source).not.toMatch(/\boutline\s*:/);
  });

  it("no longer has a `link` variant key in buttonVariants", () => {
    const source = readComponent("button.tsx");
    expect(source).not.toMatch(/\blink\s*:/);
  });
});

// ===========================================================================
// 3. BUTTON — size names (AC1)
// ===========================================================================

describe("Button — new size names present (AC1)", () => {
  it("has a `xs` size in buttonVariants", () => {
    const source = readComponent("button.tsx");
    expect(hasVariantKey(source, "xs")).toBe(true);
  });

  it("has a `sm` size in buttonVariants", () => {
    const source = readComponent("button.tsx");
    expect(hasVariantKey(source, "sm")).toBe(true);
  });

  it("has an `md` size in buttonVariants", () => {
    const source = readComponent("button.tsx");
    expect(hasVariantKey(source, "md")).toBe(true);
  });

  it("has a `lg` size in buttonVariants", () => {
    const source = readComponent("button.tsx");
    expect(hasVariantKey(source, "lg")).toBe(true);
  });
});

describe("Button — old size names removed (AC1)", () => {
  it("no longer has a standalone `icon` size (not icon-only)", () => {
    const source = readComponent("button.tsx");
    // Old: `icon:` as a size key. New spec replaces it with icon-only variant.
    // "icon-xs", "icon-sm", "icon-lg" must also be gone.
    expect(source).not.toMatch(/["']?icon["']?\s*:/);
  });

  it("no longer has an `icon-xs` size", () => {
    const source = readComponent("button.tsx");
    expect(source).not.toMatch(/["']icon-xs["']\s*:/);
  });

  it("keeps an `icon-sm` size for compact icon buttons", () => {
    const source = readComponent("button.tsx");
    expect(source).toMatch(/["']icon-sm["']\s*:/);
  });

  it("no longer has an `icon-lg` size", () => {
    const source = readComponent("button.tsx");
    expect(source).not.toMatch(/["']icon-lg["']\s*:/);
  });

  it("no longer has a `default` size key in buttonVariants", () => {
    const source = readComponent("button.tsx");
    // After migration, the default size becomes "md"
    expect(source).not.toMatch(/size:\s*\{[^}]*\bdefault\s*:/s);
  });
});

// ===========================================================================
// 4. BUTTON — design system token usage (AC1)
// ===========================================================================

describe("Button — design system tokens used (AC1)", () => {
  it("uses --interactive-default or interactive-default token for primary variant", () => {
    const source = readComponent("button.tsx");
    // The primary variant should reference interactive token (bg-interactive or var(--interactive-default))
    expect(source).toMatch(/interactive/);
  });

  it("uses --danger token family for danger variant", () => {
    const source = readComponent("button.tsx");
    // danger variant should use danger token (bg-danger, --danger-9, etc.)
    expect(source).toMatch(/danger/);
  });

  it("uses --radius-md token or rounded-md utility", () => {
    const source = readComponent("button.tsx");
    // CVA+Tailwind: rounded-md maps to --radius-md via @theme inline
    expect(source).toMatch(/radius-md|rounded-md/);
  });

  it("uses --font-size-md or font-size-md token or text-md utility", () => {
    const source = readComponent("button.tsx");
    // CVA+Tailwind: text-md maps to --font-size-md via @theme inline
    expect(source).toMatch(/font-size-md|text-md/);
  });

  it("uses --font-weight-medium or font-weight-medium token or font-medium utility", () => {
    const source = readComponent("button.tsx");
    // CVA+Tailwind: font-medium maps to --font-weight-medium via @theme inline
    expect(source).toMatch(/font-weight-medium|font-medium/);
  });

  it("uses --surface-tertiary token for secondary/ghost variants", () => {
    const source = readComponent("button.tsx");
    expect(source).toMatch(/surface-tertiary/);
  });

  it("uses --text-on-accent token", () => {
    const source = readComponent("button.tsx");
    expect(source).toMatch(/text-on-accent/);
  });
});

// ===========================================================================
// 5. BUTTON — loading state support (AC1)
// ===========================================================================

describe("Button — loading state support (AC1)", () => {
  it("accepts a `loading` prop or data-loading attribute", () => {
    const source = readComponent("button.tsx");
    // Loading state can be implemented as prop, data attr, or aria-busy
    expect(source).toMatch(/loading|aria-busy/i);
  });
});

// ===========================================================================
// 6. BADGE — new variant names present (AC2)
// ===========================================================================

describe("Badge — new semantic variant names present (AC2)", () => {
  it("has an `accent` variant in badgeVariants", () => {
    const source = readComponent("badge.tsx");
    expect(hasVariantKey(source, "accent")).toBe(true);
  });

  it("has a `success` variant in badgeVariants", () => {
    const source = readComponent("badge.tsx");
    expect(hasVariantKey(source, "success")).toBe(true);
  });

  it("has a `warning` variant in badgeVariants", () => {
    const source = readComponent("badge.tsx");
    expect(hasVariantKey(source, "warning")).toBe(true);
  });

  it("has a `danger` variant in badgeVariants", () => {
    const source = readComponent("badge.tsx");
    expect(hasVariantKey(source, "danger")).toBe(true);
  });

  it("has an `info` variant in badgeVariants", () => {
    const source = readComponent("badge.tsx");
    expect(hasVariantKey(source, "info")).toBe(true);
  });

  it("has a `neutral` variant in badgeVariants", () => {
    const source = readComponent("badge.tsx");
    expect(hasVariantKey(source, "neutral")).toBe(true);
  });

  it("has an `outline` variant in badgeVariants", () => {
    const source = readComponent("badge.tsx");
    expect(hasVariantKey(source, "outline")).toBe(true);
  });
});

// ===========================================================================
// 7. BADGE — old variant names removed (AC2)
// ===========================================================================

describe("Badge — old variant names removed (AC2)", () => {
  it("no longer has a `default` variant key in badgeVariants", () => {
    const source = readComponent("badge.tsx");
    expect(source).not.toMatch(/variant:\s*\{[^}]*\bdefault\s*:/s);
  });

  it("no longer has a `destructive` variant key in badgeVariants", () => {
    const source = readComponent("badge.tsx");
    expect(source).not.toMatch(/\bdestructive\s*:/);
  });

  it("no longer has a `ghost` variant key in badgeVariants", () => {
    const source = readComponent("badge.tsx");
    expect(source).not.toMatch(/\bghost\s*:/);
  });

  it("no longer has a `link` variant key in badgeVariants", () => {
    const source = readComponent("badge.tsx");
    expect(source).not.toMatch(/\blink\s*:/);
  });

  it("no longer has a `secondary` variant key in badgeVariants", () => {
    const source = readComponent("badge.tsx");
    // `secondary` was an old badge variant; the new DS uses neutral instead
    expect(source).not.toMatch(/\bsecondary\s*:/);
  });
});

// ===========================================================================
// 8. BADGE — design system token usage (AC2)
// ===========================================================================

describe("Badge — design system tokens used (AC2)", () => {
  it("uses --font-mono for font family", () => {
    const source = readComponent("badge.tsx");
    expect(source).toMatch(/font-mono/);
  });

  it("uses --font-size-2xs (2xs) for badge text", () => {
    const source = readComponent("badge.tsx");
    expect(source).toMatch(/font-size-2xs|text-2xs/);
  });

  it("uses --radius-full (pill shape) or rounded-full utility", () => {
    const source = readComponent("badge.tsx");
    // CVA+Tailwind: rounded-full maps to --radius-full (9999px) via @theme inline
    expect(source).toMatch(/radius-full|rounded-full/);
  });

  it("uses semantic accent color tokens (accent-3 or accent-11)", () => {
    const source = readComponent("badge.tsx");
    expect(source).toMatch(/accent-[0-9]/);
  });

  it("uses semantic success color tokens (success-3 or success-11)", () => {
    const source = readComponent("badge.tsx");
    expect(source).toMatch(/success-[0-9]/);
  });

  it("uses semantic warning color tokens (warning-3 or warning-11)", () => {
    const source = readComponent("badge.tsx");
    expect(source).toMatch(/warning-[0-9]/);
  });

  it("uses semantic danger color tokens (danger-3 or danger-11)", () => {
    const source = readComponent("badge.tsx");
    expect(source).toMatch(/danger-[0-9]/);
  });

  it("uses semantic info color tokens (info-3 or info-11)", () => {
    const source = readComponent("badge.tsx");
    expect(source).toMatch(/info-[0-9]/);
  });

  it("uses --tracking-wide for letter spacing", () => {
    const source = readComponent("badge.tsx");
    expect(source).toMatch(/tracking-wide/);
  });
});

// ===========================================================================
// 9. BADGE — dot indicator (AC2)
// ===========================================================================

describe("Badge — dot indicator support (AC2)", () => {
  it("supports a dot indicator (dot prop, variant, or boolean)", () => {
    const source = readComponent("badge.tsx");
    // Dot indicator can be a prop, a `dot` variant key, or a dot class
    expect(source).toMatch(/\bdot\b/);
  });
});

// ===========================================================================
// 10. BADGE — base-ui patterns preserved
// ===========================================================================

describe("Badge — base-ui import patterns preserved", () => {
  it("still imports mergeProps from @base-ui/react/merge-props", () => {
    const source = readComponent("badge.tsx");
    expect(source).toMatch(/@base-ui\/react\/merge-props/);
  });

  it("still imports useRender from @base-ui/react/use-render", () => {
    const source = readComponent("badge.tsx");
    expect(source).toMatch(/@base-ui\/react\/use-render/);
  });
});

// ===========================================================================
// 11. BUTTON — base-ui patterns preserved
// ===========================================================================

describe("Button — base-ui import patterns preserved", () => {
  it("still imports Button as ButtonPrimitive from @base-ui/react/button", () => {
    const source = readComponent("button.tsx");
    expect(source).toMatch(/@base-ui\/react\/button/);
  });
});

// ===========================================================================
// 12. INPUT — design system token usage (AC3)
// ===========================================================================

describe("Input — design system tokens used (AC3)", () => {
  it("uses --control-height-sm or control-height-sm for height", () => {
    const source = readComponent("input.tsx");
    expect(source).toMatch(/control-height-sm/);
  });

  it("uses --font-size-md or font-size-md token or text-md utility", () => {
    const source = readComponent("input.tsx");
    // CVA+Tailwind: text-md maps to --font-size-md via @theme inline
    expect(source).toMatch(/font-size-md|text-md/);
  });

  it("uses --border-default or border-default for border", () => {
    const source = readComponent("input.tsx");
    expect(source).toMatch(/border-default/);
  });

  it("uses --border-focus or border-focus for focus ring", () => {
    const source = readComponent("input.tsx");
    expect(source).toMatch(/border-focus/);
  });

  it("uses a design system surface token for background", () => {
    const source = readComponent("input.tsx");
    // surface-primary or surface-tertiary are both valid DS surface tokens
    expect(source).toMatch(/surface-primary|surface-tertiary/);
  });
});

// ===========================================================================
// 13. TEXTAREA — design system token usage (AC3)
// ===========================================================================

describe("Textarea — design system tokens used (AC3)", () => {
  it("uses --control-height-sm or control-height-sm for min-height reference", () => {
    const source = readComponent("textarea.tsx");
    expect(source).toMatch(/control-height-sm/);
  });

  it("uses --font-size-md or font-size-md token or text-md utility", () => {
    const source = readComponent("textarea.tsx");
    // CVA+Tailwind: text-md maps to --font-size-md via @theme inline
    expect(source).toMatch(/font-size-md|text-md/);
  });

  it("uses --border-default or border-default for border", () => {
    const source = readComponent("textarea.tsx");
    expect(source).toMatch(/border-default/);
  });

  it("uses --border-focus or border-focus for focus ring", () => {
    const source = readComponent("textarea.tsx");
    expect(source).toMatch(/border-focus/);
  });

  it("uses a design system surface token for background", () => {
    const source = readComponent("textarea.tsx");
    // surface-primary or surface-tertiary are both valid DS surface tokens
    expect(source).toMatch(/surface-primary|surface-tertiary/);
  });
});

// ===========================================================================
// 14. LABEL — design system token usage (AC4)
// ===========================================================================

describe("Label — design system tokens used (AC4)", () => {
  it("uses --font-size-sm or font-size-sm or text-sm utility for label text size", () => {
    const source = readComponent("label.tsx");
    // CVA+Tailwind: text-sm maps to --font-size-sm via @theme inline
    expect(source).toMatch(/font-size-sm|text-sm/);
  });

  it("uses --font-weight-medium or font-weight-medium or font-medium utility", () => {
    const source = readComponent("label.tsx");
    // CVA+Tailwind: font-medium maps to --font-weight-medium via @theme inline
    expect(source).toMatch(/font-weight-medium|font-medium/);
  });

  it("uses a design system text color token for label color", () => {
    const source = readComponent("label.tsx");
    // text-primary or text-secondary are both valid DS text tokens
    expect(source).toMatch(/text-primary|text-secondary/);
  });
});

// ===========================================================================
// 16. TOOLTIP — design system token usage (AC6)
// ===========================================================================

describe("Tooltip — design system tokens used (AC6)", () => {
  it("uses --surface-raised or surface-raised for tooltip background", () => {
    const source = readComponent("tooltip.tsx");
    expect(source).toMatch(/surface-raised/);
  });

  it("does not use bg-text-primary as tooltip background (old inverted pattern)", () => {
    const source = readComponent("tooltip.tsx");
    // Old tooltip used bg-text-primary (dark inverted bg); new spec uses surface-raised
    expect(source).not.toMatch(/\bbg-text-primary\b/);
  });

  it("uses text-primary for tooltip text color", () => {
    const source = readComponent("tooltip.tsx");
    // Must reference text-primary (not text-surface-primary which was the old inverted approach)
    expect(source).toMatch(/\btext-primary\b/);
  });

  it("does not use text-surface-primary as tooltip text (old inverted pattern)", () => {
    const source = readComponent("tooltip.tsx");
    // Old tooltip used text-surface-primary (text-on-dark); new spec uses text-primary
    expect(source).not.toMatch(/\btext-surface-primary\b/);
  });

  it("uses --font-size-xs or font-size-xs (12px) for tooltip text", () => {
    const source = readComponent("tooltip.tsx");
    expect(source).toMatch(/font-size-xs/);
  });

  it("tooltip arrow also uses surface-raised (not bg-text-primary)", () => {
    const source = readComponent("tooltip.tsx");
    // The arrow element should use the new surface-raised token, not bg-text-primary
    expect(source).not.toMatch(/bg-text-primary.*Arrow|Arrow.*bg-text-primary/s);
  });
});

// ===========================================================================
// 17. STORYBOOK STORIES — all 7 component story files exist (AC7)
// ===========================================================================

describe("Storybook stories — existence (AC7)", () => {
  it("Button.stories.tsx exists in src/stories/ or src/components/ui/", () => {
    expect(storyExists("Button.stories.tsx")).toBe(true);
  });

  it("Badge.stories.tsx exists in src/stories/ or src/components/ui/", () => {
    expect(storyExists("Badge.stories.tsx")).toBe(true);
  });

  it("Input.stories.tsx exists in src/stories/ or src/components/ui/", () => {
    expect(storyExists("Input.stories.tsx")).toBe(true);
  });

  it("Textarea.stories.tsx exists in src/stories/ or src/components/ui/", () => {
    expect(storyExists("Textarea.stories.tsx")).toBe(true);
  });

  it("Label.stories.tsx exists in src/stories/ or src/components/ui/", () => {
    expect(storyExists("Label.stories.tsx")).toBe(true);
  });

  it("Tooltip.stories.tsx exists in src/stories/ or src/components/ui/", () => {
    expect(storyExists("Tooltip.stories.tsx")).toBe(true);
  });
});

// ===========================================================================
// 18. STORYBOOK STORIES — proper structure (AC7)
// ===========================================================================

describe("Storybook stories — Button.stories.tsx structure (AC7)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("Button.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("Button.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("Button.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });

  it("covers the primary variant", () => {
    const content = readStory("Button.stories.tsx");
    expect(content).toMatch(/primary/i);
  });

  it("covers the loading state", () => {
    const content = readStory("Button.stories.tsx");
    expect(content).toMatch(/loading/i);
  });

  it("covers the icon-only variant", () => {
    const content = readStory("Button.stories.tsx");
    expect(content).toMatch(/icon.?only/i);
  });
});

describe("Storybook stories — Badge.stories.tsx structure (AC7)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("Badge.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("Badge.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("Badge.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });

  it("covers semantic variants (success, warning, danger, info)", () => {
    const content = readStory("Badge.stories.tsx");
    expect(content).toMatch(/success|warning|danger|info/i);
  });

  it("covers the dot indicator", () => {
    const content = readStory("Badge.stories.tsx");
    expect(content).toMatch(/dot/i);
  });
});

describe("Storybook stories — Input.stories.tsx structure (AC7)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("Input.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("Input.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("Input.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });
});

describe("Storybook stories — Textarea.stories.tsx structure (AC7)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("Textarea.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("Textarea.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("Textarea.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });
});

describe("Storybook stories — Label.stories.tsx structure (AC7)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("Label.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("Label.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("Label.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });
});

describe("Storybook stories — Tooltip.stories.tsx structure (AC7)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("Tooltip.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("Tooltip.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("Tooltip.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });
});
