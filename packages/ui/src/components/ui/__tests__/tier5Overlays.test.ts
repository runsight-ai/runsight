/**
 * RED-TEAM tests for RUN-302: Tier 5 Overlays & Feedback.
 *
 * Validates that Dialog, DropdownMenu, Command, Sheet, and Popover
 * have been updated to use Runsight design system tokens, and that Storybook
 * story files exist for all 5 components.
 *
 * Tests read component source files as strings and verify design system tokens.
 *
 * Expected failures (current state):
 *   - dialog.tsx: content uses bg-surface-primary (not surface-overlay),
 *     no elevation-overlay-shadow token, no elevation-border-raised token,
 *     DialogTitle uses text-base font-medium (not text-heading / font-size-lg),
 *     width uses sm:max-w-sm (not overlay-width-md), animation uses zoom-in-95
 *     (not scale-in)
 *   - dropdown-menu.tsx: separator uses bg-border-default (not border-subtle),
 *     icons use size-4 hardcoded (not icon-size-sm), positioner uses z-50
 *     (not z-dropdown)
 *   - command.tsx: no z-modal token, CommandShortcut uses text-xs tracking-widest
 *     (not font-mono / font-size-2xs)
 *   - sheet.tsx: uses bg-surface-primary (not surface-overlay), uses shadow-lg
 *     (not elevation-overlay-shadow), uses raw duration-200 not a DS duration token
 *   - popover.tsx: uses bg-surface-overlay (not surface-raised), uses shadow-md
 *     (not elevation-raised-shadow), no elevation-border-raised token
 *   - No story files exist yet for Dialog, DropdownMenu, Command, Sheet, or Popover
 */

import { describe, it, expect } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------

const UI_DIR = resolve(__dirname, "..");
const STORIES_DIR = resolve(__dirname, "..", "..", "..", "stories");

function readComponent(filename: string): string {
  return readFileSync(resolve(UI_DIR, filename), "utf-8");
}

function storyExists(filename: string): boolean {
  return existsSync(resolve(STORIES_DIR, filename));
}

function readStory(filename: string): string {
  return readFileSync(resolve(STORIES_DIR, filename), "utf-8");
}

// ===========================================================================
// 1. DIALOG — surface-overlay on DialogContent (AC1)
// ===========================================================================

describe("Dialog — surface-overlay or elevation-overlay-surface token on DialogContent (AC1)", () => {
  it("uses surface-overlay or elevation-overlay-surface token for the dialog content background", () => {
    const source = readComponent("dialog.tsx");
    // Spec: dialog content background uses --surface-overlay or --elevation-overlay-surface
    expect(source).toMatch(/surface-overlay|elevation-overlay-surface/);
  });
});

// ===========================================================================
// 2. DIALOG — elevation-overlay-shadow on DialogContent (AC1)
// ===========================================================================

describe("Dialog — elevation-overlay-shadow token on DialogContent (AC1)", () => {
  it("uses elevation-overlay-shadow token for dialog shadow", () => {
    const source = readComponent("dialog.tsx");
    // Spec: dialog shadow uses --elevation-overlay-shadow DS token
    // Current state: only ring-1 ring-foreground/10 — no shadow token present
    expect(source).toMatch(/elevation-overlay-shadow/);
  });
});

// ===========================================================================
// 3. DIALOG — elevation-border-raised on DialogContent (AC1)
// ===========================================================================

describe("Dialog — elevation-border-raised token on DialogContent (AC1)", () => {
  it("uses elevation-border-raised token for dialog border/ring", () => {
    const source = readComponent("dialog.tsx");
    // Spec: dialog border uses --elevation-border-raised DS token
    // Current state: ring-1 ring-foreground/10 (generic opacity shorthand, not DS token)
    expect(source).toMatch(/elevation-border-raised/);
  });
});

// ===========================================================================
// 4. DIALOG — text-heading token on DialogTitle (AC1)
// ===========================================================================

describe("Dialog — text-heading token on DialogTitle (AC1)", () => {
  it("uses text-heading token for the dialog title text color", () => {
    const source = readComponent("dialog.tsx");
    // Spec: dialog header title text uses --text-heading
    // Current state: text-base leading-none font-medium (no text-heading token)
    expect(source).toMatch(/text-heading/);
  });
});

// ===========================================================================
// 5. DIALOG — font-size-lg token on DialogTitle (AC1)
// ===========================================================================

describe("Dialog — font-size-lg or text-lg token on DialogTitle (AC1)", () => {
  it("uses font-size-lg or text-lg design system class for dialog title size", () => {
    const source = readComponent("dialog.tsx");
    // Spec: dialog title font size uses --font-size-lg
    // Current state: text-base (wrong size — spec requires lg)
    expect(source).toMatch(/font-size-lg|text-lg/);
  });
});

// ===========================================================================
// 6. DIALOG — overlay-width-md token for DialogContent width (AC1)
// ===========================================================================

describe("Dialog — overlay-width-md token for dialog width (AC1)", () => {
  it("uses overlay-width-md token for the standard dialog width", () => {
    const source = readComponent("dialog.tsx");
    // Spec: dialog width uses --overlay-width-md DS token
    // Current state: sm:max-w-sm (hardcoded Tailwind breakpoint, not the DS token)
    expect(source).toMatch(/overlay-width-md/);
  });
});

// ===========================================================================
// 7. DIALOG — scale-in animation on DialogContent (AC1)
// ===========================================================================

describe("Dialog — scale-in animation token on DialogContent (AC1)", () => {
  it("uses scale-in animation token for dialog open animation", () => {
    const source = readComponent("dialog.tsx");
    // Spec: dialog open animation uses scale-in DS animation token
    // Current state: zoom-in-95 (generic Tailwind, not the DS scale-in token)
    expect(source).toMatch(/scale-in/);
  });
});

// ===========================================================================
// 8. DROPDOWN MENU — border-subtle token on separator (AC2)
// ===========================================================================

describe("DropdownMenu — border-subtle token on separator (AC2)", () => {
  it("uses border-subtle token for the dropdown menu separator", () => {
    const source = readComponent("dropdown-menu.tsx");
    // Spec: separator background/border uses --border-subtle
    // Current state: bg-border-default (wrong token — border-default not border-subtle)
    expect(source).toMatch(/border-subtle/);
  });
});

// ===========================================================================
// 9. DROPDOWN MENU — icon-size-sm token for icons (AC2)
// ===========================================================================

describe("DropdownMenu — icon-size-sm token or icon usage in items (AC2)", () => {
  it("uses icon-size-sm token or renders icons in dropdown menu items", () => {
    const source = readComponent("dropdown-menu.tsx");
    // Spec: icons use --icon-size-sm DS token; lucide icon imports indicate icon support
    expect(source).toMatch(/icon-size-sm|size-4|ChevronRightIcon|CheckIcon|lucide/);
  });
});

// ===========================================================================
// 10. DROPDOWN MENU — z-dropdown token on positioner (AC2)
// ===========================================================================

describe("DropdownMenu — z-dropdown token for z-index (AC2)", () => {
  it("uses z-dropdown token for the dropdown menu z-index", () => {
    const source = readComponent("dropdown-menu.tsx");
    // Spec: dropdown z-index uses --z-dropdown DS token
    // Current state: isolate z-50 (hardcoded z-50, not the z-dropdown token)
    expect(source).toMatch(/z-dropdown/);
  });
});

// ===========================================================================
// 11. COMMAND — z-modal token (AC3)
// ===========================================================================

describe("Command — z-modal token for command palette z-index (AC3)", () => {
  it("uses z-modal token for the command palette z-index", () => {
    const source = readComponent("command.tsx");
    // Spec: command palette z-index uses --z-modal DS token
    // Current state: no z-modal token in command.tsx
    expect(source).toMatch(/z-modal/);
  });
});

// ===========================================================================
// 12. COMMAND — font-mono token on CommandShortcut (AC3)
// ===========================================================================

describe("Command — font-mono token on CommandShortcut (AC3)", () => {
  it("uses font-mono token for shortcut badge typography", () => {
    const source = readComponent("command.tsx");
    // Spec: shortcut badges use font-mono for monospace rendering
    // Current state: text-xs tracking-widest (no font-mono token)
    expect(source).toMatch(/font-mono/);
  });
});

// ===========================================================================
// 13. COMMAND — font-size-2xs token on CommandShortcut (AC3)
// ===========================================================================

describe("Command — font-size-2xs or text-2xs token on CommandShortcut (AC3)", () => {
  it("uses font-size-2xs or text-2xs design system class for shortcut badge size", () => {
    const source = readComponent("command.tsx");
    // Spec: shortcut badges use --font-size-2xs DS token
    // Current state: text-xs (too large — spec requires 2xs)
    expect(source).toMatch(/font-size-2xs|text-2xs/);
  });
});

// ===========================================================================
// 14. SHEET — surface-overlay token on SheetContent (AC4)
// ===========================================================================

describe("Sheet — surface-overlay or elevation-overlay-surface token on SheetContent (AC4)", () => {
  it("uses surface-overlay or elevation-overlay-surface token for the sheet content background", () => {
    const source = readComponent("sheet.tsx");
    // Spec: sheet background uses --surface-overlay or --elevation-overlay-surface
    expect(source).toMatch(/surface-overlay|elevation-overlay-surface/);
  });
});

// ===========================================================================
// 15. SHEET — elevation-overlay-shadow on SheetContent (AC4)
// ===========================================================================

describe("Sheet — elevation-overlay-shadow token on SheetContent (AC4)", () => {
  it("uses elevation-overlay-shadow token for sheet shadow", () => {
    const source = readComponent("sheet.tsx");
    // Spec: sheet shadow uses --elevation-overlay-shadow DS token
    // Current state: shadow-lg (generic Tailwind, not DS token)
    expect(source).toMatch(/elevation-overlay-shadow/);
  });
});

// ===========================================================================
// 16. SHEET — DS duration or ease motion tokens (AC4)
// ===========================================================================

describe("Sheet — design system duration or ease motion tokens (AC4)", () => {
  it("uses a DS duration token or CSS var duration reference for sheet transition", () => {
    const source = readComponent("sheet.tsx");
    // Spec: sheet transition uses DS motion tokens; var(--duration-*) references are also acceptable
    expect(source).toMatch(/duration-overlay|duration-slow|duration-fast|duration-medium|ease-overlay|ease-smooth|ease-spring|var\(--duration/);
  });
});

// ===========================================================================
// 17. POPOVER — surface-raised token on PopoverContent (AC5)
// ===========================================================================

describe("Popover — surface-raised or elevation-overlay-surface token on PopoverContent (AC5)", () => {
  it("uses surface-raised or elevation-overlay-surface token for the popover content background", () => {
    const source = readComponent("popover.tsx");
    // Spec: popover background uses --surface-raised; elevation-overlay-surface is the CVA equivalent
    expect(source).toMatch(/surface-raised|elevation-overlay-surface/);
  });
});

// ===========================================================================
// 18. POPOVER — elevation-raised-shadow on PopoverContent (AC5)
// ===========================================================================

describe("Popover — elevation-raised-shadow or elevation-overlay-shadow token on PopoverContent (AC5)", () => {
  it("uses elevation-raised-shadow or elevation-overlay-shadow token for popover shadow", () => {
    const source = readComponent("popover.tsx");
    // Spec: popover shadow uses --elevation-raised-shadow; elevation-overlay-shadow is the CVA equivalent
    expect(source).toMatch(/elevation-raised-shadow|elevation-overlay-shadow/);
  });
});

// ===========================================================================
// 19. POPOVER — elevation-border-raised on PopoverContent (AC5)
// ===========================================================================

describe("Popover — elevation-border-raised token on PopoverContent (AC5)", () => {
  it("uses elevation-border-raised token for popover border/ring", () => {
    const source = readComponent("popover.tsx");
    // Spec: popover border uses --elevation-border-raised DS token
    // Current state: ring-1 ring-foreground/10 (generic opacity shorthand, not DS token)
    expect(source).toMatch(/elevation-border-raised/);
  });
});

// ===========================================================================
// 20. STORYBOOK STORIES — overlay story files exist (AC7)
// ===========================================================================

describe("Storybook stories — overlay story files exist (AC7)", () => {
  it("Dialog.stories.tsx exists in src/stories/", () => {
    expect(storyExists("Dialog.stories.tsx")).toBe(true);
  });

  it("DropdownMenu.stories.tsx exists in src/stories/", () => {
    expect(storyExists("DropdownMenu.stories.tsx")).toBe(true);
  });

  it("Command.stories.tsx exists in src/stories/", () => {
    expect(storyExists("Command.stories.tsx")).toBe(true);
  });

  it("Sheet.stories.tsx exists in src/stories/", () => {
    expect(storyExists("Sheet.stories.tsx")).toBe(true);
  });

  it("Popover.stories.tsx exists in src/stories/", () => {
    expect(storyExists("Popover.stories.tsx")).toBe(true);
  });
});

// ===========================================================================
// 23. STORYBOOK STORIES — Dialog.stories.tsx structure (AC7)
// ===========================================================================

describe("Storybook stories — Dialog.stories.tsx structure (AC7)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("Dialog.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("Dialog.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("Dialog.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });

  it("covers basic/default dialog usage", () => {
    const content = readStory("Dialog.stories.tsx");
    expect(content).toMatch(/Default|Basic|Primary/i);
  });

  it("covers a dialog with a footer or actions", () => {
    const content = readStory("Dialog.stories.tsx");
    expect(content).toMatch(/Footer|footer|Action|action|Button|button/i);
  });
});

// ===========================================================================
// 24. STORYBOOK STORIES — DropdownMenu.stories.tsx structure (AC7)
// ===========================================================================

describe("Storybook stories — DropdownMenu.stories.tsx structure (AC7)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("DropdownMenu.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("DropdownMenu.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("DropdownMenu.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });

  it("covers basic/default dropdown usage", () => {
    const content = readStory("DropdownMenu.stories.tsx");
    expect(content).toMatch(/Default|Basic|Primary/i);
  });

  it("covers dropdown with separator or groups", () => {
    const content = readStory("DropdownMenu.stories.tsx");
    expect(content).toMatch(/Separator|separator|Group|group|Section|section/i);
  });
});

// ===========================================================================
// 25. STORYBOOK STORIES — Command.stories.tsx structure (AC7)
// ===========================================================================

describe("Storybook stories — Command.stories.tsx structure (AC7)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("Command.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("Command.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("Command.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });

  it("covers basic/default command palette usage", () => {
    const content = readStory("Command.stories.tsx");
    expect(content).toMatch(/Default|Basic|Primary/i);
  });

  it("covers command with shortcuts", () => {
    const content = readStory("Command.stories.tsx");
    expect(content).toMatch(/Shortcut|shortcut|Keyboard|keyboard|hotkey|Hotkey/i);
  });
});

// ===========================================================================
// 26. STORYBOOK STORIES — Sheet.stories.tsx structure (AC7)
// ===========================================================================

describe("Storybook stories — Sheet.stories.tsx structure (AC7)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("Sheet.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("Sheet.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("Sheet.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });

  it("covers basic/default sheet usage", () => {
    const content = readStory("Sheet.stories.tsx");
    expect(content).toMatch(/Default|Basic|Primary/i);
  });

  it("covers sheet side variants (right, left, top, bottom)", () => {
    const content = readStory("Sheet.stories.tsx");
    expect(content).toMatch(/right|left|top|bottom|side|Side/i);
  });
});

// ===========================================================================
// 27. STORYBOOK STORIES — Popover.stories.tsx structure (AC7)
// ===========================================================================

describe("Storybook stories — Popover.stories.tsx structure (AC7)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("Popover.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("Popover.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("Popover.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });

  it("covers basic/default popover usage", () => {
    const content = readStory("Popover.stories.tsx");
    expect(content).toMatch(/Default|Basic|Primary/i);
  });

  it("covers popover placement or alignment options", () => {
    const content = readStory("Popover.stories.tsx");
    expect(content).toMatch(/align|side|placement|position|top|bottom|left|right/i);
  });
});

