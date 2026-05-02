/**
 * Token architecture coverage for globals.css.
 *
 * Governance: Stable style-system coverage for design tokens and global CSS
 * contracts that package consumers rely on.
 * Owner: packages/ui design-system maintainers.
 * Boundary: Read-only assertions against packages/ui/src/styles/globals.css;
 * this suite does not touch runtime state, user-authored assets, browser
 * harnesses, or remote integrations.
 * Exit criteria: Keep this suite focused on enduring token architecture,
 * Tailwind bridge, retired token absence, global styles/a11y/sidebar behavior;
 * move unrelated behavior to owner-specific style suites.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const GLOBALS_PATH = resolve(__dirname, "..", "globals.css");

const FONT_IMPORTS_REMOVED = [
  "@fontsource-variable/inter",
  "@fontsource-variable/jetbrains-mono",
] as const;

const SYSTEM_TOKEN_GROUPS = {
  surface: [
    "primary",
    "secondary",
    "tertiary",
    "raised",
    "overlay",
    "sunken",
    "hover",
    "active",
    "selected",
  ],
  text: [
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
  ],
  border: [
    "subtle",
    "default",
    "hover",
    "accent",
    "focus",
    "danger",
    "success",
    "warning",
    "info",
  ],
  interactive: ["default", "hover", "active", "muted"],
} as const;

const SEMANTIC_HUE_STEPS = {
  success: [3, 7, 9, 11],
  warning: [3, 7, 9, 11],
  danger: [3, 7, 8, 9, 10, 11],
  info: [3, 7, 9, 11],
} as const;

const OLD_THEME_MAPPINGS = [
  "--color-background",
  "--color-foreground",
  "--color-primary-foreground",
  "--color-card",
  "--color-destructive",
  "--color-muted-foreground",
  "--color-accent-foreground",
  "--color-popover",
  "--color-popover-foreground",
  "--color-secondary-foreground",
  "--color-ring",
  "--color-input",
  "--color-border",
  "--color-surface",
  "--color-surface-elevated",
  "--color-error",
  "--color-running",
] as const;

const OLD_ROOT_TOKENS = [
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
  "--error",
  "--error-hover",
  "--running",
  "--node-soul",
  "--node-task",
  "--node-team",
  "--node-branch",
] as const;

const OLD_ALPHA_TOKENS = [
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
] as const;

function readGlobals(): string {
  return readFileSync(GLOBALS_PATH, "utf-8");
}

function extractBlock(css: string, selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = css.match(
    new RegExp(`${escaped}\\s*\\{([^}]*(?:\\{[^}]*\\}[^}]*)*)\\}`, "s")
  );
  return match?.[1] ?? "";
}

function extractThemeInlineBlock(css: string): string {
  const match = css.match(/@theme\s+inline\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}/s);
  return match?.[1] ?? "";
}

function cssProperty(name: string): RegExp {
  return new RegExp(`(?<![\\w-])${escapeRegExp(name)}\\s*:`);
}

function expectProperties(source: string, names: readonly string[]): void {
  for (const name of names) {
    expect(source).toMatch(cssProperty(name));
  }
}

function expectNoProperties(source: string, names: readonly string[]): void {
  for (const name of names) {
    expect(source).not.toMatch(cssProperty(name));
  }
}

function numericTokens(prefix: string, start: number, end: number): string[] {
  return Array.from(
    { length: end - start + 1 },
    (_, index) => `--${prefix}-${start + index}`
  );
}

function namedTokens(prefix: string, names: readonly string[]): string[] {
  return names.map((name) => `--${prefix}-${name}`);
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

describe("token architecture reference and system tokens", () => {
  it("loads approved font faces and exposes font family variables", () => {
    const css = readGlobals();

    for (const oldImport of FONT_IMPORTS_REMOVED) {
      expect(css).not.toMatch(
        new RegExp(`@import\\s+["']${escapeRegExp(oldImport)}["']`)
      );
    }

    expect(css).toMatch(/@font-face\s*\{[^}]*font-family:\s*["']Geist["']/s);
    expect(css).toMatch(/@font-face\s*\{[^}]*url\([^)]*geist/is);
    expect(css).toMatch(
      /@font-face\s*\{[^}]*font-family:\s*["']JetBrains Mono["']/s
    );
    expect(css).toMatch(/@font-face\s*\{[^)]*jetbrains/is);
    expect(/@import\s+url\([^)]*api\.fontshare\.com[^)]*Satoshi/i.test(css) || /Satoshi/i.test(css)).toBe(true);
    expectProperties(css, ["--font-display", "--font-body", "--font-mono"]);
  });

  it("defines reference color scales without hex values in :root", () => {
    const root = extractBlock(readGlobals(), ":root");
    const scaledTokens = [
      ...numericTokens("neutral", 1, 12),
      ...numericTokens("accent", 1, 12),
      ...numericTokens("chart", 1, 8),
      ...namedTokens("block", ["agent", "logic", "control", "utility", "custom"]),
      ...namedTokens("syntax", ["key", "string", "value", "comment", "punct"]),
      ...Object.entries(SEMANTIC_HUE_STEPS).flatMap(([prefix, steps]) =>
        steps.map((step) => `--${prefix}-${step}`)
      ),
    ];

    expectProperties(root, scaledTokens);
    for (const name of [...numericTokens("neutral", 1, 12), ...numericTokens("accent", 1, 12)]) {
      const value = root.match(new RegExp(`${escapeRegExp(name)}\\s*:\\s*([^;]+)`))?.[1];
      expect(value).toBeDefined();
      expect(value).not.toMatch(/#[0-9a-fA-F]{3,8}/);
    }
    expect(root.match(/:\s*#[0-9a-fA-F]{3,8}\s*[;,)]/g)).toBeNull();
  });

  it("defines typography, spacing, layout, motion, and focus primitives", () => {
    const css = readGlobals();

    expectProperties(css, [
      ...namedTokens("font-size", ["2xs", "xs", "sm", "md", "lg", "xl", "2xl", "3xl"]),
      ...numericTokens("space", 0, 12),
      ...namedTokens("gap", ["condensed", "normal", "spacious"]),
      ...namedTokens("padding", ["condensed", "normal", "spacious"]),
      "--radius-md",
    ]);
    expect(css).toMatch(/--line-height-/);
    expect(css).toMatch(/--font-weight-/);
    expect(css).toMatch(/--tracking-/);
    expect(css).toMatch(/--z-/);
    expect(css).toMatch(/--control-height-/);
    expect(css).toMatch(/--border-width-/);
    expect(css).toMatch(/--duration-/);
    expect(css).toMatch(/--ease-/);
    expect(css).toMatch(/--icon-/);
    expect(css).toMatch(/--focus-/);
    expect(css).toMatch(/--radius-md\s*:\s*4px/);
  });

  it("defines semantic system tokens for surfaces, text, borders, interactive states, and elevation", () => {
    const root = extractBlock(readGlobals(), ":root");

    for (const [prefix, names] of Object.entries(SYSTEM_TOKEN_GROUPS)) {
      expectProperties(root, namedTokens(prefix, names));
    }
    expect(readGlobals()).toMatch(/--elevation-/);
  });

  it("supports density and light theme overrides", () => {
    const css = readGlobals();
    const lightTheme = extractBlock(css, '[data-theme="light"]');

    expect(css).toMatch(/\[data-density=["']compact["']\]/);
    expect(css).toMatch(/\[data-density=["']comfortable["']\]/);
    expect(/--control-height-/.test(extractBlock(css, ":root")) || /\[data-density=["']default["']\]/.test(css)).toBe(true);
    expect(extractBlock(css, ":root")).toMatch(/--surface-primary\s*:/);
    expect(css).toMatch(/\[data-theme=["']light["']\]/);
    expect(lightTheme).toMatch(/--neutral-/);
  });
});

describe("Tailwind bridge token mappings", () => {
  it("maps design-system colors and radii through @theme inline", () => {
    const theme = extractThemeInlineBlock(readGlobals());

    expectProperties(theme, [
      ...namedTokens("color-surface", ["primary", "secondary", "tertiary", "raised", "overlay"]),
      ...namedTokens("color-border", ["subtle", "default", "hover"]),
      ...namedTokens("color", ["success", "warning", "danger", "info"]),
      ...numericTokens("color-chart", 1, 8),
      ...namedTokens("color-block", ["agent", "logic", "control", "utility", "custom"]),
      "--color-interactive-hover",
      "--radius-md",
    ]);

    for (const text of ["heading", "primary", "secondary", "muted"]) {
      expect(cssProperty(`--color-text-${text}`).test(theme) || cssProperty(`--color-${text}`).test(theme)).toBe(true);
    }
    expect(/--color-interactive-default\s*:|--color-interactive\s*:/.test(theme)).toBe(true);
    expect(theme).not.toMatch(/--radius-md\s*:\s*var\(--radius\)/);
    expect(theme).not.toMatch(/--radius-sm\s*:\s*calc\(/);
  });
});

describe("retired token absence", () => {
  it("omits old theme aliases from @theme inline", () => {
    const theme = extractThemeInlineBlock(readGlobals());

    expectNoProperties(theme, OLD_THEME_MAPPINGS);
    expect(theme).not.toMatch(/--color-node-/);
  });

  it("omits old root tokens and alpha variants from :root", () => {
    const root = extractBlock(readGlobals(), ":root");

    expectNoProperties(root, OLD_ROOT_TOKENS);
    expectNoProperties(root, OLD_ALPHA_TOKENS);
  });
});

describe("global styles/a11y/sidebar contracts", () => {
  it("retains required imports and animation keyframes", () => {
    const css = readGlobals();

    for (const imported of ["tailwindcss", "tw-animate-css", "shadcn/tailwind.css"]) {
      expect(css).toMatch(new RegExp(`@import\\s+["']${escapeRegExp(imported)}["']`));
    }
    for (const keyframe of ["fade-in", "slide-up", "scale-in", "spin", "pulse", "shimmer"]) {
      expect(css).toMatch(new RegExp(`@keyframes\\s+${keyframe}`));
    }
    expect((css.match(/@keyframes\s+float/g) ?? []).length).toBeLessThanOrEqual(1);
  });

  it("keeps reset, body, and accessibility styles on design-system tokens", () => {
    const css = readGlobals();
    const body = extractBlock(css, "body");

    expect(css).toMatch(/box-sizing\s*:\s*border-box/);
    expect(body).not.toMatch(/--background\b|--foreground\b|bg-background|text-foreground/);
    expect(css).toMatch(/prefers-reduced-motion/);
    expect(css).toMatch(/focus-visible|focus-ring|--focus-/);
    expect(css).toMatch(/scrollbar/);
  });

  it("defines sidebar tokens as design-system references without old sidebar names", () => {
    const css = readGlobals();
    const sidebarTokens = [
      "--sidebar-bg",
      "--sidebar-fg",
      "--sidebar-border",
      "--sidebar-accent",
      "--sidebar-accent-fg",
      "--sidebar-muted",
      "--sidebar-hover",
      "--sidebar-active-indicator",
    ];

    expectProperties(css, sidebarTokens);
    expect(css).toMatch(/--sidebar-bg\s*:\s*var\(/);
    expect(css).toMatch(/--sidebar-fg\s*:\s*var\(/);
    expect(css).toMatch(/--sidebar-border\s*:\s*var\(/);
    expectNoProperties(css, ["--sidebar", "--sidebar-foreground"]);
  });
});
