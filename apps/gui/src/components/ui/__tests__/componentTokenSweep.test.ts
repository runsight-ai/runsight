/**
 * RED-TEAM tests for RUN-295: Component Token Reference Sweep.
 *
 * Validates that all 19 UI components have been updated to use the Runsight
 * Product Design System token names. Tests read each component file as a
 * string and assert:
 *   1. No OLD shadcn token class names or var() references remain
 *   2. At least some NEW design system token names are present (proving
 *      the file was updated, not just emptied)
 *
 * Expected failures (current state):
 *   - All components still reference old shadcn token names
 *   - bg-primary, bg-secondary, bg-muted, bg-card, bg-background, etc.
 *   - text-foreground, text-primary-foreground, text-muted-foreground, etc.
 *   - border-border, border-input, ring-ring
 *   - var(--background), var(--foreground), var(--primary), etc.
 *
 * Token mapping (old -> new):
 *   bg-background        -> bg-surface-primary
 *   bg-card              -> bg-surface-secondary
 *   bg-popover           -> bg-surface-overlay
 *   bg-primary           -> bg-interactive
 *   bg-secondary         -> bg-surface-tertiary
 *   bg-muted             -> bg-surface-tertiary
 *   bg-accent            -> bg-surface-hover
 *   bg-destructive       -> bg-danger
 *   text-foreground      -> text-primary or text-heading
 *   text-primary-foreground -> text-on-accent
 *   text-muted-foreground   -> text-muted
 *   text-card-foreground    -> text-primary
 *   text-popover-foreground -> text-primary
 *   text-secondary-foreground -> text-primary
 *   text-accent-foreground  -> text-primary
 *   text-destructive     -> text-danger
 *   border-border        -> border-border-default
 *   border-input         -> border-border-default
 *   ring-ring            -> ring-border-focus
 *   var(--background)    -> var(--surface-primary)
 *   var(--foreground)    -> var(--text-primary)
 *   var(--primary)       -> var(--interactive-default)  [exact, not --primary-foreground]
 *   var(--border)        -> var(--border-default)
 *   var(--card)          -> var(--surface-secondary)
 *   var(--muted)         -> var(--surface-tertiary)
 *   var(--ring)          -> var(--border-focus)
 *   var(--destructive)   -> var(--danger-9)
 *   var(--input)         -> var(--border-default)
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const UI_DIR = resolve(__dirname, "..");

function readComponent(filename: string): string {
  return readFileSync(resolve(UI_DIR, filename), "utf-8");
}

/**
 * Returns all occurrences of old Tailwind class tokens in the source string.
 *
 * Uses word-boundary-aware patterns to avoid false positives:
 *   - `bg-primary` must NOT match `bg-primary-foreground`
 *   - `bg-muted` must NOT match `text-muted-foreground`
 *   - `border-border` matches the literal Tailwind class
 *   - `text-primary-foreground` IS an old token and must be matched
 */
function findOldTailwindTokens(source: string): string[] {
  // Each entry: [displayName, regex]
  // Patterns use a negative lookahead so that e.g. "bg-primary" does not
  // match "bg-primary-foreground".
  const patterns: Array<[string, RegExp]> = [
    // bg- tokens — old shadcn utility classes
    ["bg-background", /\bbg-background\b/g],
    ["bg-card", /\bbg-card\b/g],
    ["bg-popover", /\bbg-popover\b/g],
    // bg-primary must NOT match bg-primary-foreground
    ["bg-primary", /\bbg-primary(?!-foreground\b)(?![\w-])/g],
    // bg-secondary must NOT match bg-secondary-foreground
    ["bg-secondary", /\bbg-secondary(?!-foreground\b)(?![\w-])/g],
    // bg-muted must NOT match bg-muted-foreground (text-muted-foreground handled separately)
    ["bg-muted", /\bbg-muted(?!-foreground\b)(?![\w-])/g],
    // bg-accent must NOT match bg-accent-foreground
    ["bg-accent", /\bbg-accent(?!-foreground\b)(?![\w-])/g],
    // bg-destructive must NOT match bg-destructive/N (opacity modifier) — it IS old
    ["bg-destructive", /\bbg-destructive(?![\w-])/g],

    // text- tokens — old shadcn utility classes
    // text-foreground: standalone, must NOT match text-foreground/N opacity suffix (still old)
    ["text-foreground", /\btext-foreground(?![\w-])/g],
    // text-primary-foreground: IS an old token (not to be confused with new text-primary)
    ["text-primary-foreground", /\btext-primary-foreground\b/g],
    // text-muted-foreground: IS an old token
    ["text-muted-foreground", /\btext-muted-foreground\b/g],
    // text-card-foreground
    ["text-card-foreground", /\btext-card-foreground\b/g],
    // text-popover-foreground
    ["text-popover-foreground", /\btext-popover-foreground\b/g],
    // text-secondary-foreground
    ["text-secondary-foreground", /\btext-secondary-foreground\b/g],
    // text-accent-foreground
    ["text-accent-foreground", /\btext-accent-foreground\b/g],
    // text-destructive: standalone (NOT text-destructive/N, which is still old but same base)
    ["text-destructive", /\btext-destructive(?![\w-])/g],

    // border- tokens — old shadcn utility classes
    // border-border: must NOT match border-border-default (new) or border-border-focus (new)
    ["border-border", /\bborder-border(?!-default\b)(?!-focus\b)(?!-hover\b)(?!-accent\b)(?!-danger\b)(?!-success\b)(?!-warning\b)(?!-info\b)(?!-subtle\b)(?![\w-])/g],
    // border-input: standalone
    ["border-input", /\bborder-input(?![\w-])/g],

    // ring- tokens
    // ring-ring: must NOT match ring-border-focus (new token contains "ring" differently)
    ["ring-ring", /\bring-ring(?![\w-])/g],
  ];

  const found: string[] = [];
  for (const [name, regex] of patterns) {
    if (regex.test(source)) {
      found.push(name);
    }
  }
  return found;
}

/**
 * Returns all occurrences of old CSS var() references in the source string.
 *
 * Uses exact closing-paren matching so that:
 *   var(--primary) does NOT match var(--primary-foreground)
 *   var(--border) does NOT match var(--border-default) (new) or var(--border-focus) (new)
 *   var(--muted) does NOT match var(--muted-foreground) (still old but different token)
 */
function findOldVarRefs(source: string): string[] {
  // Each entry: [displayName, regex]
  // All patterns use \) to require the exact closing paren, preventing
  // partial matches like var(--primary-foreground).
  const patterns: Array<[string, RegExp]> = [
    ["var(--background)", /var\(--background\)/g],
    ["var(--foreground)", /var\(--foreground\)/g],
    // var(--primary) must NOT match var(--primary-foreground)
    ["var(--primary)", /var\(--primary\)/g],
    // var(--border) must NOT match var(--border-default), var(--border-focus), etc.
    ["var(--border)", /var\(--border\)/g],
    ["var(--card)", /var\(--card\)/g],
    // var(--muted) must NOT match var(--muted-foreground)
    ["var(--muted)", /var\(--muted\)/g],
    ["var(--ring)", /var\(--ring\)/g],
    ["var(--destructive)", /var\(--destructive\)/g],
    ["var(--input)", /var\(--input\)/g],
  ];

  const found: string[] = [];
  for (const [name, regex] of patterns) {
    if (regex.test(source)) {
      found.push(name);
    }
  }
  return found;
}

/**
 * Checks that a source string contains at least one new design system token,
 * proving the file was updated and not simply emptied.
 */
function hasNewTokens(source: string): boolean {
  const newTokenPatterns = [
    /\bbg-surface-/,
    /\bbg-interactive\b/,
    /\bbg-danger\b/,
    /\bbg-surface-hover\b/,
    /\btext-on-accent\b/,
    /\btext-muted(?!-foreground)(?![\w-])/,
    /\btext-danger\b/,
    /\btext-heading\b/,
    /\bborder-border-default\b/,
    /\bring-border-focus\b/,
    /var\(--surface-primary\)/,
    /var\(--surface-secondary\)/,
    /var\(--surface-tertiary\)/,
    /var\(--surface-overlay\)/,
    /var\(--text-primary\)/,
    /var\(--interactive-default\)/,
    /var\(--border-default\)/,
    /var\(--border-focus\)/,
    /var\(--danger-9\)/,
  ];
  return newTokenPatterns.some((p) => p.test(source));
}

// ---------------------------------------------------------------------------
// The 19 component files to check
// ---------------------------------------------------------------------------

const COMPONENTS: string[] = [
  "badge.tsx",
  "button.tsx",
  "card.tsx",
  "command.tsx",
  "dialog.tsx",
  "dropdown-menu.tsx",
  "input-group.tsx",
  "input.tsx",
  "label.tsx",
  "popover.tsx",
  "scroll-area.tsx",
  "select.tsx",
  "separator.tsx",
  "sheet.tsx",
  "switch.tsx",
  "table.tsx",
  "tabs.tsx",
  "textarea.tsx",
  "tooltip.tsx",
];

// ===========================================================================
// 1. All 19 component files exist and are readable
// ===========================================================================

describe("Component files exist", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} exists and is non-empty`, () => {
      const source = readComponent(filename);
      expect(source.length).toBeGreaterThan(0);
    });
  }
});

// ===========================================================================
// 2. No old Tailwind token class names — per component (AC1, AC2, AC3)
// ===========================================================================

describe("No old Tailwind tokens — badge.tsx", () => {
  it("contains no old shadcn Tailwind class tokens", () => {
    const source = readComponent("badge.tsx");
    const found = findOldTailwindTokens(source);
    expect(found).toEqual([]);
  });
});

describe("No old Tailwind tokens — button.tsx", () => {
  it("contains no old shadcn Tailwind class tokens", () => {
    const source = readComponent("button.tsx");
    const found = findOldTailwindTokens(source);
    expect(found).toEqual([]);
  });
});

describe("No old Tailwind tokens — card.tsx", () => {
  it("contains no old shadcn Tailwind class tokens", () => {
    const source = readComponent("card.tsx");
    const found = findOldTailwindTokens(source);
    expect(found).toEqual([]);
  });
});

describe("No old Tailwind tokens — command.tsx", () => {
  it("contains no old shadcn Tailwind class tokens", () => {
    const source = readComponent("command.tsx");
    const found = findOldTailwindTokens(source);
    expect(found).toEqual([]);
  });
});

describe("No old Tailwind tokens — dialog.tsx", () => {
  it("contains no old shadcn Tailwind class tokens", () => {
    const source = readComponent("dialog.tsx");
    const found = findOldTailwindTokens(source);
    expect(found).toEqual([]);
  });
});

describe("No old Tailwind tokens — dropdown-menu.tsx", () => {
  it("contains no old shadcn Tailwind class tokens", () => {
    const source = readComponent("dropdown-menu.tsx");
    const found = findOldTailwindTokens(source);
    expect(found).toEqual([]);
  });
});

describe("No old Tailwind tokens — input-group.tsx", () => {
  it("contains no old shadcn Tailwind class tokens", () => {
    const source = readComponent("input-group.tsx");
    const found = findOldTailwindTokens(source);
    expect(found).toEqual([]);
  });
});

describe("No old Tailwind tokens — input.tsx", () => {
  it("contains no old shadcn Tailwind class tokens", () => {
    const source = readComponent("input.tsx");
    const found = findOldTailwindTokens(source);
    expect(found).toEqual([]);
  });
});

describe("No old Tailwind tokens — label.tsx", () => {
  it("contains no old shadcn Tailwind class tokens", () => {
    const source = readComponent("label.tsx");
    const found = findOldTailwindTokens(source);
    expect(found).toEqual([]);
  });
});

describe("No old Tailwind tokens — popover.tsx", () => {
  it("contains no old shadcn Tailwind class tokens", () => {
    const source = readComponent("popover.tsx");
    const found = findOldTailwindTokens(source);
    expect(found).toEqual([]);
  });
});

describe("No old Tailwind tokens — scroll-area.tsx", () => {
  it("contains no old shadcn Tailwind class tokens", () => {
    const source = readComponent("scroll-area.tsx");
    const found = findOldTailwindTokens(source);
    expect(found).toEqual([]);
  });
});

describe("No old Tailwind tokens — select.tsx", () => {
  it("contains no old shadcn Tailwind class tokens", () => {
    const source = readComponent("select.tsx");
    const found = findOldTailwindTokens(source);
    expect(found).toEqual([]);
  });
});

describe("No old Tailwind tokens — separator.tsx", () => {
  it("contains no old shadcn Tailwind class tokens", () => {
    const source = readComponent("separator.tsx");
    const found = findOldTailwindTokens(source);
    expect(found).toEqual([]);
  });
});

describe("No old Tailwind tokens — sheet.tsx", () => {
  it("contains no old shadcn Tailwind class tokens", () => {
    const source = readComponent("sheet.tsx");
    const found = findOldTailwindTokens(source);
    expect(found).toEqual([]);
  });
});

describe("No old Tailwind tokens — switch.tsx", () => {
  it("contains no old shadcn Tailwind class tokens", () => {
    const source = readComponent("switch.tsx");
    const found = findOldTailwindTokens(source);
    expect(found).toEqual([]);
  });
});

describe("No old Tailwind tokens — table.tsx", () => {
  it("contains no old shadcn Tailwind class tokens", () => {
    const source = readComponent("table.tsx");
    const found = findOldTailwindTokens(source);
    expect(found).toEqual([]);
  });
});

describe("No old Tailwind tokens — tabs.tsx", () => {
  it("contains no old shadcn Tailwind class tokens", () => {
    const source = readComponent("tabs.tsx");
    const found = findOldTailwindTokens(source);
    expect(found).toEqual([]);
  });
});

describe("No old Tailwind tokens — textarea.tsx", () => {
  it("contains no old shadcn Tailwind class tokens", () => {
    const source = readComponent("textarea.tsx");
    const found = findOldTailwindTokens(source);
    expect(found).toEqual([]);
  });
});

describe("No old Tailwind tokens — tooltip.tsx", () => {
  it("contains no old shadcn Tailwind class tokens", () => {
    const source = readComponent("tooltip.tsx");
    const found = findOldTailwindTokens(source);
    expect(found).toEqual([]);
  });
});

// ===========================================================================
// 3. No old CSS var() references — per component (AC1, AC2, AC3)
// ===========================================================================

describe("No old var() refs — badge.tsx", () => {
  it("contains no old CSS var() token references", () => {
    const source = readComponent("badge.tsx");
    const found = findOldVarRefs(source);
    expect(found).toEqual([]);
  });
});

describe("No old var() refs — button.tsx", () => {
  it("contains no old CSS var() token references", () => {
    const source = readComponent("button.tsx");
    const found = findOldVarRefs(source);
    expect(found).toEqual([]);
  });
});

describe("No old var() refs — card.tsx", () => {
  it("contains no old CSS var() token references", () => {
    const source = readComponent("card.tsx");
    const found = findOldVarRefs(source);
    expect(found).toEqual([]);
  });
});

describe("No old var() refs — command.tsx", () => {
  it("contains no old CSS var() token references", () => {
    const source = readComponent("command.tsx");
    const found = findOldVarRefs(source);
    expect(found).toEqual([]);
  });
});

describe("No old var() refs — dialog.tsx", () => {
  it("contains no old CSS var() token references", () => {
    const source = readComponent("dialog.tsx");
    const found = findOldVarRefs(source);
    expect(found).toEqual([]);
  });
});

describe("No old var() refs — dropdown-menu.tsx", () => {
  it("contains no old CSS var() token references", () => {
    const source = readComponent("dropdown-menu.tsx");
    const found = findOldVarRefs(source);
    expect(found).toEqual([]);
  });
});

describe("No old var() refs — input-group.tsx", () => {
  it("contains no old CSS var() token references", () => {
    const source = readComponent("input-group.tsx");
    const found = findOldVarRefs(source);
    expect(found).toEqual([]);
  });
});

describe("No old var() refs — input.tsx", () => {
  it("contains no old CSS var() token references", () => {
    const source = readComponent("input.tsx");
    const found = findOldVarRefs(source);
    expect(found).toEqual([]);
  });
});

describe("No old var() refs — label.tsx", () => {
  it("contains no old CSS var() token references", () => {
    const source = readComponent("label.tsx");
    const found = findOldVarRefs(source);
    expect(found).toEqual([]);
  });
});

describe("No old var() refs — popover.tsx", () => {
  it("contains no old CSS var() token references", () => {
    const source = readComponent("popover.tsx");
    const found = findOldVarRefs(source);
    expect(found).toEqual([]);
  });
});

describe("No old var() refs — scroll-area.tsx", () => {
  it("contains no old CSS var() token references", () => {
    const source = readComponent("scroll-area.tsx");
    const found = findOldVarRefs(source);
    expect(found).toEqual([]);
  });
});

describe("No old var() refs — select.tsx", () => {
  it("contains no old CSS var() token references", () => {
    const source = readComponent("select.tsx");
    const found = findOldVarRefs(source);
    expect(found).toEqual([]);
  });
});

describe("No old var() refs — separator.tsx", () => {
  it("contains no old CSS var() token references", () => {
    const source = readComponent("separator.tsx");
    const found = findOldVarRefs(source);
    expect(found).toEqual([]);
  });
});

describe("No old var() refs — sheet.tsx", () => {
  it("contains no old CSS var() token references", () => {
    const source = readComponent("sheet.tsx");
    const found = findOldVarRefs(source);
    expect(found).toEqual([]);
  });
});

describe("No old var() refs — switch.tsx", () => {
  it("contains no old CSS var() token references", () => {
    const source = readComponent("switch.tsx");
    const found = findOldVarRefs(source);
    expect(found).toEqual([]);
  });
});

describe("No old var() refs — table.tsx", () => {
  it("contains no old CSS var() token references", () => {
    const source = readComponent("table.tsx");
    const found = findOldVarRefs(source);
    expect(found).toEqual([]);
  });
});

describe("No old var() refs — tabs.tsx", () => {
  it("contains no old CSS var() token references", () => {
    const source = readComponent("tabs.tsx");
    const found = findOldVarRefs(source);
    expect(found).toEqual([]);
  });
});

describe("No old var() refs — textarea.tsx", () => {
  it("contains no old CSS var() token references", () => {
    const source = readComponent("textarea.tsx");
    const found = findOldVarRefs(source);
    expect(found).toEqual([]);
  });
});

describe("No old var() refs — tooltip.tsx", () => {
  it("contains no old CSS var() token references", () => {
    const source = readComponent("tooltip.tsx");
    const found = findOldVarRefs(source);
    expect(found).toEqual([]);
  });
});

// ===========================================================================
// 4. CVA variant names are unchanged (AC5) — spot-check key components
// ===========================================================================

// Updated by RUN-298: badge variants migrated to design system spec
// Old variants (default, secondary, destructive, ghost, link) replaced with
// semantic variants (accent, success, warning, danger, info, neutral, outline)
describe("CVA variant names updated — badge.tsx (RUN-298)", () => {
  it("exports badgeVariants with new semantic variants: accent, success, warning, danger, info, neutral, outline", () => {
    const source = readComponent("badge.tsx");
    expect(source).toMatch(/export.*badgeVariants/);
    // New variant names in the CVA config
    expect(source).toMatch(/variant:\s*\{/);
    expect(source).toMatch(/\baccent\b/);
    expect(source).toMatch(/\bsuccess\b/);
    expect(source).toMatch(/\bwarning\b/);
    expect(source).toMatch(/\bdanger\b/);
    expect(source).toMatch(/\binfo\b/);
    expect(source).toMatch(/\bneutral\b/);
    expect(source).toMatch(/\boutline\b/);
  });
});

// Updated by RUN-298: button variants migrated to design system spec
// Old variants (default, outline, destructive, link) replaced with
// new variants (primary, danger, icon-only) and updated secondary/ghost
describe("CVA variant names updated — button.tsx (RUN-298)", () => {
  it("exports buttonVariants with new design system variants: primary, secondary, ghost, danger, icon-only", () => {
    const source = readComponent("button.tsx");
    expect(source).toMatch(/export.*buttonVariants/);
    expect(source).toMatch(/variant:\s*\{/);
    expect(source).toMatch(/\bprimary\b/);
    expect(source).toMatch(/\bsecondary\b/);
    expect(source).toMatch(/\bghost\b/);
    expect(source).toMatch(/\bdanger\b/);
    expect(source).toMatch(/["']icon-only["']/);
  });
});

// ===========================================================================
// 5. New design system tokens ARE present after sweep (AC3, AC4)
//    Tests will pass only once Green Team has done the rename.
//    Components confirmed to have old tokens today: badge, button, card,
//    command, dialog, dropdown-menu, input-group, input, popover, scroll-area,
//    select, sheet, switch, table, tabs, textarea.
// ===========================================================================

describe("New tokens present after sweep — components with confirmed old tokens", () => {
  const confirmed = [
    "badge.tsx",
    "button.tsx",
    "card.tsx",
    "command.tsx",
    "dialog.tsx",
    "dropdown-menu.tsx",
    "input-group.tsx",
    "input.tsx",
    "popover.tsx",
    "scroll-area.tsx",
    "select.tsx",
    "sheet.tsx",
    "switch.tsx",
    "table.tsx",
    "tabs.tsx",
    "textarea.tsx",
  ];

  for (const filename of confirmed) {
    it(`${filename} contains at least one new design system token`, () => {
      const source = readComponent(filename);
      expect(hasNewTokens(source)).toBe(true);
    });
  }
});

// ===========================================================================
// 6. Comprehensive grep — each old token absent across ALL 19 components (AC2)
//    Grouped by token for clear failure messages when grepping.
// ===========================================================================

describe("Token sweep completeness: bg-background absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no bg-background`, () => {
      expect(readComponent(filename)).not.toMatch(/\bbg-background\b/);
    });
  }
});

describe("Token sweep completeness: bg-card absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no bg-card`, () => {
      expect(readComponent(filename)).not.toMatch(/\bbg-card\b/);
    });
  }
});

describe("Token sweep completeness: bg-popover absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no bg-popover`, () => {
      expect(readComponent(filename)).not.toMatch(/\bbg-popover\b/);
    });
  }
});

describe("Token sweep completeness: bg-primary absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no bg-primary (standalone, not -foreground)`, () => {
      // bg-primary followed by end of token or opacity modifier (e.g. /80) — still old
      expect(readComponent(filename)).not.toMatch(/\bbg-primary(?!-foreground\b)(?![\w-])/);
    });
  }
});

describe("Token sweep completeness: bg-secondary absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no bg-secondary (standalone, not -foreground)`, () => {
      expect(readComponent(filename)).not.toMatch(/\bbg-secondary(?!-foreground\b)(?![\w-])/);
    });
  }
});

describe("Token sweep completeness: bg-muted absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no bg-muted (standalone)`, () => {
      expect(readComponent(filename)).not.toMatch(/\bbg-muted(?!-foreground\b)(?![\w-])/);
    });
  }
});

describe("Token sweep completeness: bg-accent absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no bg-accent (standalone, not -foreground)`, () => {
      expect(readComponent(filename)).not.toMatch(/\bbg-accent(?!-foreground\b)(?![\w-])/);
    });
  }
});

describe("Token sweep completeness: bg-destructive absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no bg-destructive`, () => {
      expect(readComponent(filename)).not.toMatch(/\bbg-destructive(?![\w-])/);
    });
  }
});

describe("Token sweep completeness: text-foreground absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no text-foreground`, () => {
      expect(readComponent(filename)).not.toMatch(/\btext-foreground(?![\w-])/);
    });
  }
});

describe("Token sweep completeness: text-primary-foreground absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no text-primary-foreground`, () => {
      expect(readComponent(filename)).not.toMatch(/\btext-primary-foreground\b/);
    });
  }
});

describe("Token sweep completeness: text-muted-foreground absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no text-muted-foreground`, () => {
      expect(readComponent(filename)).not.toMatch(/\btext-muted-foreground\b/);
    });
  }
});

describe("Token sweep completeness: text-card-foreground absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no text-card-foreground`, () => {
      expect(readComponent(filename)).not.toMatch(/\btext-card-foreground\b/);
    });
  }
});

describe("Token sweep completeness: text-popover-foreground absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no text-popover-foreground`, () => {
      expect(readComponent(filename)).not.toMatch(/\btext-popover-foreground\b/);
    });
  }
});

describe("Token sweep completeness: text-secondary-foreground absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no text-secondary-foreground`, () => {
      expect(readComponent(filename)).not.toMatch(/\btext-secondary-foreground\b/);
    });
  }
});

describe("Token sweep completeness: text-accent-foreground absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no text-accent-foreground`, () => {
      expect(readComponent(filename)).not.toMatch(/\btext-accent-foreground\b/);
    });
  }
});

describe("Token sweep completeness: text-destructive absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no text-destructive`, () => {
      expect(readComponent(filename)).not.toMatch(/\btext-destructive(?![\w-])/);
    });
  }
});

describe("Token sweep completeness: border-border (old) absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no border-border (old — not border-border-default)`, () => {
      // Must not match border-border that is NOT followed by -default/-focus/-hover etc.
      expect(readComponent(filename)).not.toMatch(
        /\bborder-border(?!-default\b)(?!-focus\b)(?!-hover\b)(?!-accent\b)(?!-danger\b)(?!-success\b)(?!-warning\b)(?!-info\b)(?!-subtle\b)(?![\w-])/
      );
    });
  }
});

describe("Token sweep completeness: border-input absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no border-input`, () => {
      expect(readComponent(filename)).not.toMatch(/\bborder-input(?![\w-])/);
    });
  }
});

describe("Token sweep completeness: ring-ring absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no ring-ring`, () => {
      expect(readComponent(filename)).not.toMatch(/\bring-ring(?![\w-])/);
    });
  }
});

describe("Token sweep completeness: var(--background) absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no var(--background)`, () => {
      expect(readComponent(filename)).not.toMatch(/var\(--background\)/);
    });
  }
});

describe("Token sweep completeness: var(--foreground) absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no var(--foreground)`, () => {
      expect(readComponent(filename)).not.toMatch(/var\(--foreground\)/);
    });
  }
});

describe("Token sweep completeness: var(--primary) absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no var(--primary) (exact, not --primary-foreground)`, () => {
      expect(readComponent(filename)).not.toMatch(/var\(--primary\)/);
    });
  }
});

describe("Token sweep completeness: var(--border) absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no var(--border) (exact)`, () => {
      expect(readComponent(filename)).not.toMatch(/var\(--border\)/);
    });
  }
});

describe("Token sweep completeness: var(--card) absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no var(--card)`, () => {
      expect(readComponent(filename)).not.toMatch(/var\(--card\)/);
    });
  }
});

describe("Token sweep completeness: var(--muted) absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no var(--muted) (exact, not --muted-foreground)`, () => {
      expect(readComponent(filename)).not.toMatch(/var\(--muted\)/);
    });
  }
});

describe("Token sweep completeness: var(--ring) absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no var(--ring)`, () => {
      expect(readComponent(filename)).not.toMatch(/var\(--ring\)/);
    });
  }
});

describe("Token sweep completeness: var(--destructive) absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no var(--destructive)`, () => {
      expect(readComponent(filename)).not.toMatch(/var\(--destructive\)/);
    });
  }
});

describe("Token sweep completeness: var(--input) absent in all components", () => {
  for (const filename of COMPONENTS) {
    it(`${filename} has no var(--input)`, () => {
      expect(readComponent(filename)).not.toMatch(/var\(--input\)/);
    });
  }
});
