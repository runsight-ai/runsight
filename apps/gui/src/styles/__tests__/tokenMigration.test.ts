/**
 * RED-TEAM tests for RUN-293: Token Migration + Tailwind Bridge.
 *
 * Validates that globals.css has been rewritten to adopt the Runsight Product
 * Design System token architecture. Tests read the CSS file as a string and
 * make structural assertions about token names, patterns, and structures.
 *
 * Expected failures (current state):
 * - globals.css still uses old shadcn hex tokens
 * - No design system reference/system tokens
 * - No @font-face declarations
 * - @theme inline block has old shadcn mappings
 * - fontsource-variable imports still present
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const GLOBALS_PATH = resolve(__dirname, "..", "globals.css");

function readGlobals(): string {
  return readFileSync(GLOBALS_PATH, "utf-8");
}

/**
 * Extract the content of the @theme inline { ... } block.
 */
function extractThemeInlineBlock(css: string): string {
  const match = css.match(/@theme\s+inline\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}/s);
  return match?.[1] ?? "";
}

/**
 * Extract the content of the :root { ... } block (first occurrence).
 */
function extractRootBlock(css: string): string {
  const match = css.match(/:root\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}/s);
  return match?.[1] ?? "";
}

// ===========================================================================
// 1. Font Loading (AC4, AC11)
// ===========================================================================

describe("Font loading", () => {
  it("does NOT import @fontsource-variable/inter", () => {
    const css = readGlobals();
    expect(css).not.toMatch(/@import\s+["']@fontsource-variable\/inter["']/);
  });

  it("does NOT import @fontsource-variable/jetbrains-mono", () => {
    const css = readGlobals();
    expect(css).not.toMatch(
      /@import\s+["']@fontsource-variable\/jetbrains-mono["']/
    );
  });

  it("has @font-face for Geist (variable, 100-900) via CDN", () => {
    const css = readGlobals();
    expect(css).toMatch(/@font-face\s*\{[^}]*font-family:\s*["']Geist["']/s);
    // Should reference a CDN URL (fontsource)
    expect(css).toMatch(/@font-face\s*\{[^}]*url\([^)]*geist/is);
  });

  it("has @font-face for JetBrains Mono (variable, 400-700) via CDN", () => {
    const css = readGlobals();
    expect(css).toMatch(
      /@font-face\s*\{[^}]*font-family:\s*["']JetBrains Mono["']/s
    );
    expect(css).toMatch(/@font-face\s*\{[^}]*url\([^)]*jetbrains/is);
  });

  it("has @import for Satoshi via Fontshare API", () => {
    const css = readGlobals();
    expect(css).toMatch(/@import\s+url\([^)]*api\.fontshare\.com[^)]*Satoshi/i);
  });

  it("defines --font-display, --font-body, and --font-mono variables", () => {
    const css = readGlobals();
    expect(css).toMatch(/--font-display\s*:/);
    expect(css).toMatch(/--font-body\s*:/);
    expect(css).toMatch(/--font-mono\s*:/);
  });
});

// ===========================================================================
// 2. Reference Tokens — Neutral Scale (AC1, AC3)
// ===========================================================================

describe("Reference tokens: neutral scale", () => {
  it("defines --neutral-1 through --neutral-12 in :root", () => {
    const root = extractRootBlock(readGlobals());
    for (let i = 1; i <= 12; i++) {
      expect(root).toMatch(new RegExp(`--neutral-${i}\\s*:`));
    }
  });

  it("neutral tokens use HSL values, not hex", () => {
    const root = extractRootBlock(readGlobals());
    // Tokens must exist AND use HSL, not hex
    const matches: string[] = [];
    for (let i = 1; i <= 12; i++) {
      const match = root.match(new RegExp(`--neutral-${i}\\s*:\\s*([^;]+)`));
      if (match) {
        matches.push(match[1]!);
        expect(match[1]).not.toMatch(/#[0-9a-fA-F]{3,8}/);
      }
    }
    // At least some neutral tokens must exist for this test to be meaningful
    expect(matches.length).toBeGreaterThan(0);
  });
});

// ===========================================================================
// 3. Reference Tokens — Accent Scale (AC1, AC3)
// ===========================================================================

describe("Reference tokens: accent scale", () => {
  it("defines --accent-1 through --accent-12 in :root", () => {
    const root = extractRootBlock(readGlobals());
    for (let i = 1; i <= 12; i++) {
      expect(root).toMatch(new RegExp(`--accent-${i}\\s*:`));
    }
  });

  it("accent tokens use HSL values, not hex", () => {
    const root = extractRootBlock(readGlobals());
    const matches: string[] = [];
    for (let i = 1; i <= 12; i++) {
      const match = root.match(new RegExp(`--accent-${i}\\s*:\\s*([^;]+)`));
      if (match) {
        matches.push(match[1]!);
        expect(match[1]).not.toMatch(/#[0-9a-fA-F]{3,8}/);
      }
    }
    // At least some accent tokens must exist for this test to be meaningful
    expect(matches.length).toBeGreaterThan(0);
  });
});

// ===========================================================================
// 4. Reference Tokens — Semantic Hue Scales (AC1)
// ===========================================================================

describe("Reference tokens: semantic hue scales", () => {
  it("defines success scale: --success-3, --success-7, --success-9, --success-11", () => {
    const root = extractRootBlock(readGlobals());
    for (const step of [3, 7, 9, 11]) {
      expect(root).toMatch(new RegExp(`--success-${step}\\s*:`));
    }
  });

  it("defines warning scale: --warning-3, --warning-7, --warning-9, --warning-11", () => {
    const root = extractRootBlock(readGlobals());
    for (const step of [3, 7, 9, 11]) {
      expect(root).toMatch(new RegExp(`--warning-${step}\\s*:`));
    }
  });

  it("defines danger scale: --danger-3, --danger-7, --danger-8, --danger-9, --danger-10, --danger-11", () => {
    const root = extractRootBlock(readGlobals());
    for (const step of [3, 7, 8, 9, 10, 11]) {
      expect(root).toMatch(new RegExp(`--danger-${step}\\s*:`));
    }
  });

  it("defines info scale: --info-3, --info-7, --info-9, --info-11", () => {
    const root = extractRootBlock(readGlobals());
    for (const step of [3, 7, 9, 11]) {
      expect(root).toMatch(new RegExp(`--info-${step}\\s*:`));
    }
  });
});

// ===========================================================================
// 5. Reference Tokens — Chart Palette (AC1)
// ===========================================================================

describe("Reference tokens: chart palette", () => {
  it("defines --chart-1 through --chart-8", () => {
    const root = extractRootBlock(readGlobals());
    for (let i = 1; i <= 8; i++) {
      expect(root).toMatch(new RegExp(`--chart-${i}\\s*:`));
    }
  });
});

// ===========================================================================
// 6. Reference Tokens — Block Category Colors (AC1)
// ===========================================================================

describe("Reference tokens: block category colors", () => {
  it("defines --block-agent, --block-logic, --block-control, --block-utility, --block-custom", () => {
    const root = extractRootBlock(readGlobals());
    for (const category of ["agent", "logic", "control", "utility", "custom"]) {
      expect(root).toMatch(new RegExp(`--block-${category}\\s*:`));
    }
  });
});

// ===========================================================================
// 7. Reference Tokens — YAML Syntax Colors (AC1)
// ===========================================================================

describe("Reference tokens: YAML syntax colors", () => {
  it("defines --syntax-key, --syntax-string, --syntax-value, --syntax-comment, --syntax-punct", () => {
    const root = extractRootBlock(readGlobals());
    for (const token of ["key", "string", "value", "comment", "punct"]) {
      expect(root).toMatch(new RegExp(`--syntax-${token}\\s*:`));
    }
  });
});

// ===========================================================================
// 8. Reference Tokens — Typography Scale (AC1)
// ===========================================================================

describe("Reference tokens: typography scale", () => {
  it("defines font-size tokens from --font-size-2xs through --font-size-3xl", () => {
    const css = readGlobals();
    for (const size of ["2xs", "xs", "sm", "md", "lg", "xl", "2xl", "3xl"]) {
      expect(css).toMatch(new RegExp(`--font-size-${size}\\s*:`));
    }
  });

  it("defines line-height tokens", () => {
    const css = readGlobals();
    expect(css).toMatch(/--line-height-/);
  });

  it("defines font-weight tokens", () => {
    const css = readGlobals();
    expect(css).toMatch(/--font-weight-/);
  });

  it("defines letter-spacing (tracking) tokens", () => {
    const css = readGlobals();
    expect(css).toMatch(/--tracking-/);
  });
});

// ===========================================================================
// 9. Reference Tokens — Spacing Scale (AC1)
// ===========================================================================

describe("Reference tokens: spacing scale", () => {
  it("defines --space-0 through --space-12", () => {
    const css = readGlobals();
    for (let i = 0; i <= 12; i++) {
      expect(css).toMatch(new RegExp(`--space-${i}\\s*:`));
    }
  });

  it("defines density context tokens (condensed, normal, spacious)", () => {
    const css = readGlobals();
    for (const density of ["condensed", "normal", "spacious"]) {
      expect(css).toMatch(new RegExp(`--gap-${density}\\s*:`));
      expect(css).toMatch(new RegExp(`--padding-${density}\\s*:`));
    }
  });
});

// ===========================================================================
// 10. Reference Tokens — Z-Index, Control Heights, Overlays, Panels (AC1)
// ===========================================================================

describe("Reference tokens: layout primitives", () => {
  it("defines z-index scale tokens", () => {
    const css = readGlobals();
    expect(css).toMatch(/--z-/);
  });

  it("defines control height tokens", () => {
    const css = readGlobals();
    expect(css).toMatch(/--control-height-/);
  });

  it("defines border-width and radius tokens with --radius-md: 4px", () => {
    const css = readGlobals();
    expect(css).toMatch(/--border-width-/);
    expect(css).toMatch(/--radius-md\s*:\s*4px/);
  });

  it("defines motion tokens (durations and easings)", () => {
    const css = readGlobals();
    expect(css).toMatch(/--duration-/);
    expect(css).toMatch(/--ease-/);
  });

  it("defines icon size tokens", () => {
    const css = readGlobals();
    expect(css).toMatch(/--icon-/);
  });

  it("defines focus/accessibility tokens", () => {
    const css = readGlobals();
    expect(css).toMatch(/--focus-/);
  });
});

// ===========================================================================
// 11. System Tokens — Surfaces (AC1)
// ===========================================================================

describe("System tokens: surfaces", () => {
  it("defines surface tokens in :root", () => {
    const root = extractRootBlock(readGlobals());
    for (const surface of [
      "primary",
      "secondary",
      "tertiary",
      "raised",
      "overlay",
      "sunken",
      "hover",
      "active",
      "selected",
    ]) {
      expect(root).toMatch(new RegExp(`--surface-${surface}\\s*:`));
    }
  });
});

// ===========================================================================
// 12. System Tokens — Text (AC1)
// ===========================================================================

describe("System tokens: text", () => {
  it("defines text tokens in :root", () => {
    const root = extractRootBlock(readGlobals());
    for (const text of [
      "heading",
      "primary",
      "secondary",
      "muted",
      "on-accent",
      "accent",
      "success",
      "warning",
      "danger",
      "info",
    ]) {
      expect(root).toMatch(new RegExp(`--text-${text}\\s*:`));
    }
  });
});

// ===========================================================================
// 13. System Tokens — Borders (AC1)
// ===========================================================================

describe("System tokens: borders", () => {
  it("defines border tokens in :root", () => {
    const root = extractRootBlock(readGlobals());
    for (const border of [
      "subtle",
      "default",
      "hover",
      "accent",
      "focus",
      "danger",
      "success",
      "warning",
      "info",
    ]) {
      expect(root).toMatch(new RegExp(`--border-${border}\\s*:`));
    }
  });
});

// ===========================================================================
// 14. System Tokens — Interactive (AC1)
// ===========================================================================

describe("System tokens: interactive", () => {
  it("defines interactive tokens in :root", () => {
    const root = extractRootBlock(readGlobals());
    for (const state of ["default", "hover", "active", "muted"]) {
      expect(root).toMatch(new RegExp(`--interactive-${state}\\s*:`));
    }
  });
});

// ===========================================================================
// 15. System Tokens — Elevation (AC1)
// ===========================================================================

describe("System tokens: elevation", () => {
  it("defines elevation system tokens", () => {
    const css = readGlobals();
    expect(css).toMatch(/--elevation-/);
  });
});

// ===========================================================================
// 16. No Hex Colors in :root (AC3)
// ===========================================================================

describe("No hex color values in :root", () => {
  it(":root contains no hex color values (#xxx or #xxxxxx)", () => {
    const root = extractRootBlock(readGlobals());
    // Find any property value that is a hex color
    const hexColorPattern = /:\s*#[0-9a-fA-F]{3,8}\s*[;,)]/g;
    const matches = root.match(hexColorPattern);
    expect(matches).toBeNull();
  });
});

// ===========================================================================
// 17. Density Modes (AC9)
// ===========================================================================

describe("Density modes", () => {
  it("has [data-density=\"compact\"] block with compact control heights", () => {
    const css = readGlobals();
    expect(css).toMatch(/\[data-density=["']compact["']\]/);
  });

  it("has [data-density=\"default\"] block or :root with default heights", () => {
    const css = readGlobals();
    // Either explicit data-density="default" or :root serves as default
    const hasDefault =
      /\[data-density=["']default["']\]/.test(css) ||
      /--control-height-/.test(extractRootBlock(css));
    expect(hasDefault).toBe(true);
  });

  it("has [data-density=\"comfortable\"] block with comfortable heights", () => {
    const css = readGlobals();
    expect(css).toMatch(/\[data-density=["']comfortable["']\]/);
  });
});

// ===========================================================================
// 18. Light Theme (AC8)
// ===========================================================================

describe("Light theme", () => {
  it("dark theme is the default (:root)", () => {
    const root = extractRootBlock(readGlobals());
    // :root should have the dark palette (neutral scale with dark HSL values)
    expect(root).toMatch(/--neutral-1\s*:/);
    expect(root).toMatch(/--surface-primary\s*:/);
  });

  it("has [data-theme=\"light\"] block with inverted neutral scale", () => {
    const css = readGlobals();
    expect(css).toMatch(/\[data-theme=["']light["']\]/);
    // The light block should redefine neutral tokens
    const lightMatch = css.match(
      /\[data-theme=["']light["']\]\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}/s
    );
    expect(lightMatch).not.toBeNull();
    if (lightMatch) {
      expect(lightMatch[1]).toMatch(/--neutral-/);
    }
  });
});

// ===========================================================================
// 19. @theme inline — New Design System Tailwind Utilities (AC5, AC6)
// ===========================================================================

describe("@theme inline: new design system token mappings", () => {
  it("maps surface tokens for Tailwind (bg-surface-primary, etc.)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    for (const surface of ["primary", "secondary", "tertiary", "raised", "overlay"]) {
      expect(theme).toMatch(
        new RegExp(`--color-surface-${surface}\\s*:`)
      );
    }
  });

  it("maps text tokens for Tailwind (text-heading, text-primary, etc.)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    for (const text of ["heading", "primary", "secondary", "muted"]) {
      expect(theme).toMatch(new RegExp(`--color-text-${text}\\s*:`));
    }
  });

  it("maps interactive tokens for Tailwind (bg-interactive, bg-interactive-hover)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).toMatch(/--color-interactive-default\s*:|--color-interactive\s*:/);
    expect(theme).toMatch(/--color-interactive-hover\s*:/);
  });

  it("maps border tokens for Tailwind (border-subtle, border-default, border-hover)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    for (const border of ["subtle", "default", "hover"]) {
      expect(theme).toMatch(
        new RegExp(`--color-border-${border}\\s*:`)
      );
    }
  });

  it("maps semantic colors for Tailwind (bg-success, bg-warning, bg-danger, bg-info)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    for (const semantic of ["success", "warning", "danger", "info"]) {
      expect(theme).toMatch(new RegExp(`--color-${semantic}\\s*:`));
    }
  });

  it("maps chart palette for Tailwind (bg-chart-1 through bg-chart-8)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    for (let i = 1; i <= 8; i++) {
      expect(theme).toMatch(new RegExp(`--color-chart-${i}\\s*:`));
    }
  });

  it("maps block category colors for Tailwind (bg-block-agent through bg-block-custom)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    for (const category of ["agent", "logic", "control", "utility", "custom"]) {
      expect(theme).toMatch(
        new RegExp(`--color-block-${category}\\s*:`)
      );
    }
  });

  it("maps radius tokens from design system (not calc-based)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).toMatch(/--radius-md\s*:/);
    // New design system uses fixed values, not calc(var(--radius) ...)
    expect(theme).not.toMatch(/--radius-md\s*:\s*var\(--radius\)/);
    expect(theme).not.toMatch(/--radius-sm\s*:\s*calc\(/);
  });
});

// ===========================================================================
// 20. @theme inline — NO Old Shadcn Token Names (AC6)
// ===========================================================================

describe("@theme inline: no backward compat aliases", () => {
  it("does NOT contain --color-background (old shadcn)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).not.toMatch(/--color-background\s*:/);
  });

  it("does NOT contain --color-foreground (old shadcn)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).not.toMatch(/--color-foreground\s*:/);
  });

  it("does NOT contain --color-primary (old shadcn)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).not.toMatch(/--color-primary\s*:/);
  });

  it("does NOT contain --color-card (old shadcn)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).not.toMatch(/--color-card\s*:/);
  });

  it("does NOT contain --color-destructive (old shadcn)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).not.toMatch(/--color-destructive\s*:/);
  });

  it("does NOT contain --color-muted (old shadcn, not text-muted)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    // Must not match --color-muted: but CAN match --color-text-muted:
    expect(theme).not.toMatch(/--color-muted\s*:/);
    expect(theme).not.toMatch(/--color-muted-foreground\s*:/);
  });

  it("does NOT contain --color-accent (old shadcn)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    // --color-accent: is old shadcn; new accent tokens are --accent-N
    expect(theme).not.toMatch(/--color-accent\s*:/);
    expect(theme).not.toMatch(/--color-accent-foreground\s*:/);
  });

  it("does NOT contain --color-popover (old shadcn)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).not.toMatch(/--color-popover\s*:/);
    expect(theme).not.toMatch(/--color-popover-foreground\s*:/);
  });

  it("does NOT contain --color-secondary (old shadcn)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).not.toMatch(/--color-secondary\s*:/);
    expect(theme).not.toMatch(/--color-secondary-foreground\s*:/);
  });

  it("does NOT contain --color-ring (old shadcn)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).not.toMatch(/--color-ring\s*:/);
  });

  it("does NOT contain --color-input (old shadcn)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).not.toMatch(/--color-input\s*:/);
  });

  it("does NOT contain --color-border (old shadcn)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).not.toMatch(/--color-border\s*:/);
  });

  it("does NOT contain --color-surface (old mapping)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    // --color-surface: is old; new are --color-surface-primary, etc.
    expect(theme).not.toMatch(/--color-surface\s*:/);
  });

  it("does NOT contain --color-surface-elevated (old mapping)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).not.toMatch(/--color-surface-elevated\s*:/);
  });

  it("does NOT contain --color-error (old mapping)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).not.toMatch(/--color-error\s*:/);
  });

  it("does NOT contain --color-running (old mapping)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).not.toMatch(/--color-running\s*:/);
  });

  it("does NOT contain --color-node-* (old node type mappings)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).not.toMatch(/--color-node-/);
  });
});

// ===========================================================================
// 21. :root — NO Legacy Shadcn Token Names (AC2)
// ===========================================================================

describe(":root: no legacy shadcn tokens", () => {
  const oldTokens = [
    "--background",
    "--foreground",
    "--primary",
    "--primary-foreground",
    "--primary-hover",
    "--secondary",
    "--secondary-foreground",
    "--card",
    "--card-foreground",
    "--popover",
    "--popover-foreground",
    "--muted",
    "--muted-foreground",
    "--muted-subtle",
    "--accent",
    "--accent-alt",
    "--accent-foreground",
    "--destructive",
    "--border",
    "--input",
    "--ring",
    "--surface",
    "--surface-elevated",
    "--surface-hover",
    "--error",
    "--error-hover",
    "--running",
    "--node-soul",
    "--node-task",
    "--node-team",
    "--node-branch",
  ];

  for (const token of oldTokens) {
    it(`does NOT contain ${token} in :root`, () => {
      const root = extractRootBlock(readGlobals());
      // Match the exact token name as a CSS property (word boundary before --)
      // Must not match tokens that start with this name but are longer
      // e.g. --surface should not match, but --surface-primary should be fine
      const escaped = token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      expect(root).not.toMatch(
        new RegExp(`(?<![\\w-])${escaped}\\s*:`)
      );
    });
  }
});

// ===========================================================================
// 22. :root — NO Old Alpha Variants (AC2)
// ===========================================================================

describe(":root: no old alpha variant tokens", () => {
  const oldAlphaTokens = [
    "--primary-05",
    "--primary-08",
    "--primary-10",
    "--primary-12",
    "--primary-30",
    "--primary-40",
    "--success-08",
    "--success-10",
    "--success-12",
    "--success-15",
    "--error-08",
    "--error-12",
    "--error-15",
    "--error-20",
    "--error-40",
    "--warning-12",
    "--running-05",
    "--running-12",
    "--muted-12",
    "--muted-15",
    "--accent-alt-12",
    "--border-10",
    "--border-15",
    "--overlay-02",
    "--background-70",
  ];

  for (const token of oldAlphaTokens) {
    it(`does NOT contain ${token}`, () => {
      const root = extractRootBlock(readGlobals());
      const escaped = token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      expect(root).not.toMatch(new RegExp(`${escaped}\\s*:`));
    });
  }
});

// ===========================================================================
// 23. Retained Imports (AC7)
// ===========================================================================

describe("Retained imports", () => {
  it("retains @import \"tailwindcss\"", () => {
    const css = readGlobals();
    expect(css).toMatch(/@import\s+["']tailwindcss["']/);
  });

  it("retains @import \"tw-animate-css\"", () => {
    const css = readGlobals();
    expect(css).toMatch(/@import\s+["']tw-animate-css["']/);
  });

  it("retains @import \"shadcn/tailwind.css\"", () => {
    const css = readGlobals();
    expect(css).toMatch(/@import\s+["']shadcn\/tailwind\.css["']/);
  });
});

// ===========================================================================
// 24. Design System Keyframes (AC10)
// ===========================================================================

describe("Design system keyframes", () => {
  it("defines @keyframes fade-in", () => {
    const css = readGlobals();
    expect(css).toMatch(/@keyframes\s+fade-in/);
  });

  it("defines @keyframes slide-up", () => {
    const css = readGlobals();
    expect(css).toMatch(/@keyframes\s+slide-up/);
  });

  it("defines @keyframes scale-in", () => {
    const css = readGlobals();
    expect(css).toMatch(/@keyframes\s+scale-in/);
  });

  it("defines @keyframes spin", () => {
    const css = readGlobals();
    expect(css).toMatch(/@keyframes\s+spin/);
  });

  it("defines @keyframes pulse", () => {
    const css = readGlobals();
    expect(css).toMatch(/@keyframes\s+pulse/);
  });

  it("defines @keyframes shimmer", () => {
    const css = readGlobals();
    expect(css).toMatch(/@keyframes\s+shimmer/);
  });

  it("does NOT have duplicate @keyframes float", () => {
    const css = readGlobals();
    const floatMatches = css.match(/@keyframes\s+float/g);
    // Should have at most 1, or 0 if float is removed entirely
    expect((floatMatches ?? []).length).toBeLessThanOrEqual(1);
  });
});

// ===========================================================================
// 25. Global Styles — Reset and Body (AC8)
// ===========================================================================

describe("Global styles: reset and body", () => {
  it("has box-sizing border-box reset", () => {
    const css = readGlobals();
    expect(css).toMatch(/box-sizing\s*:\s*border-box/);
  });

  it("body styles use design system tokens (not old tokens)", () => {
    const css = readGlobals();
    // Body should reference design system tokens like --surface-primary, --text-primary, --font-body
    // Must not reference old shadcn names in any form (variable refs OR Tailwind utilities)
    const bodyMatch = css.match(/body\s*\{([^}]+)\}/s);
    expect(bodyMatch).not.toBeNull();
    if (bodyMatch) {
      expect(bodyMatch[1]).not.toMatch(/--background\b/);
      expect(bodyMatch[1]).not.toMatch(/--foreground\b/);
      expect(bodyMatch[1]).not.toMatch(/bg-background/);
      expect(bodyMatch[1]).not.toMatch(/text-foreground/);
    }
  });
});

// ===========================================================================
// 26. Accessibility Features
// ===========================================================================

describe("Accessibility features", () => {
  it("has reduced-motion media query", () => {
    const css = readGlobals();
    expect(css).toMatch(/prefers-reduced-motion/);
  });

  it("has focus ring styles", () => {
    const css = readGlobals();
    expect(css).toMatch(/focus-visible|focus-ring|--focus-/);
  });

  it("has scrollbar styling", () => {
    const css = readGlobals();
    expect(css).toMatch(/scrollbar/);
  });
});

// ===========================================================================
// 27. Sidebar Component Tokens
// ===========================================================================

describe("Sidebar component tokens", () => {
  it("defines sidebar tokens using design system references", () => {
    const css = readGlobals();
    // New token names must exist
    expect(css).toMatch(/--sidebar-bg\s*:/);
    expect(css).toMatch(/--sidebar-fg\s*:/);
    expect(css).toMatch(/--sidebar-border\s*:/);
    expect(css).toMatch(/--sidebar-accent\s*:/);
    expect(css).toMatch(/--sidebar-accent-fg\s*:/);
    expect(css).toMatch(/--sidebar-muted\s*:/);
    expect(css).toMatch(/--sidebar-hover\s*:/);
    expect(css).toMatch(/--sidebar-active-indicator\s*:/);
    // Sidebar tokens must reference design system tokens via var(), not raw hex values
    expect(css).toMatch(/--sidebar-bg\s*:\s*var\(/);
    expect(css).toMatch(/--sidebar-fg\s*:\s*var\(/);
    expect(css).toMatch(/--sidebar-border\s*:\s*var\(/);
    // Old sidebar token names must be absent
    expect(css).not.toMatch(/--sidebar\s*:/);
    expect(css).not.toMatch(/--sidebar-foreground\s*:/);
  });
});
