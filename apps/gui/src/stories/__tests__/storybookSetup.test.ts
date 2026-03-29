/**
 * RED-TEAM tests for RUN-297: Storybook Init + Design Token Integration.
 *
 * Verifies that Storybook config files exist, are properly configured with
 * the design system, and that the DesignTokens documentation story is in place.
 *
 * Expected failures (current state):
 * - .storybook/ directory does not exist
 * - .storybook/main.ts does not exist
 * - .storybook/preview.ts does not exist
 * - src/stories/DesignTokens.stories.tsx does not exist
 * - package.json missing storybook / build-storybook scripts
 * - package.json missing @storybook/react-vite and storybook devDependencies
 */

import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Paths — all relative to apps/gui/
// ---------------------------------------------------------------------------

const GUI_ROOT = resolve(__dirname, "..", "..", "..");
const STORYBOOK_DIR = resolve(GUI_ROOT, ".storybook");
const MAIN_TS = resolve(STORYBOOK_DIR, "main.ts");
const PREVIEW_TS = resolve(STORYBOOK_DIR, "preview.ts");
const DESIGN_TOKENS_STORY = resolve(
  GUI_ROOT,
  "src",
  "stories",
  "DesignTokens.stories.tsx"
);
const PACKAGE_JSON = resolve(GUI_ROOT, "package.json");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function readFile(filePath: string): string {
  return readFileSync(filePath, "utf-8");
}

function readPackageJson(): {
  scripts?: Record<string, string>;
  devDependencies?: Record<string, string>;
} {
  return JSON.parse(readFile(PACKAGE_JSON));
}

// ===========================================================================
// 1. .storybook/main.ts — Config file existence and structure (AC1, AC5)
// ===========================================================================

describe(".storybook/main.ts — existence and framework config", () => {
  it("file exists at .storybook/main.ts", () => {
    expect(existsSync(MAIN_TS)).toBe(true);
  });

  it("references @storybook/react-vite as the framework", () => {
    const content = readFile(MAIN_TS);
    expect(content).toMatch(/@storybook\/react-vite/);
  });

  it("has a stories glob pattern pointing to src/**/*.stories", () => {
    const content = readFile(MAIN_TS);
    // Must point to story files inside src/
    expect(content).toMatch(/\.\.\/src\/\*\*\/\*\.stories/);
  });

  it("story glob covers both .ts and .tsx extensions", () => {
    const content = readFile(MAIN_TS);
    // Pattern must include tsx (and ts) — e.g. @(ts|tsx) or {ts,tsx}
    expect(content).toMatch(/tsx/);
  });

  it("viteFinal or vite config includes @tailwindcss/vite plugin for Tailwind v4 compat", () => {
    const content = readFile(MAIN_TS);
    // Must wire up @tailwindcss/vite so design tokens are available in stories
    expect(content).toMatch(/@tailwindcss\/vite/);
  });
});

// ===========================================================================
// 2. .storybook/preview.ts — Design system integration (AC2, AC3, AC4)
// ===========================================================================

describe(".storybook/preview.ts — existence and design system imports", () => {
  it("file exists at .storybook/preview.ts", () => {
    expect(existsSync(PREVIEW_TS)).toBe(true);
  });

  it("imports globals.css (design system tokens)", () => {
    const content = readFile(PREVIEW_TS);
    // Must import the globals.css that carries all design tokens
    expect(content).toMatch(/\.\.\/src\/styles\/globals\.css/);
  });

  it("sets dark background as default in parameters", () => {
    const content = readFile(PREVIEW_TS);
    // Storybook background parameter: backgrounds.default = 'dark'
    expect(content).toMatch(/backgrounds/);
    expect(content).toMatch(/dark/);
  });

  it("configures a dark background option with a dark hex/HSL color value", () => {
    const content = readFile(PREVIEW_TS);
    // A named 'dark' background must have a color value.
    expect(content).toMatch(/name.*dark|dark.*name/i);
    expect(content).toMatch(/value\s*:/);
  });

  it("loads Geist font", () => {
    const content = readFile(PREVIEW_TS);
    expect(content).toMatch(/[Gg]eist/);
  });

  it("loads JetBrains Mono font", () => {
    const content = readFile(PREVIEW_TS);
    expect(content).toMatch(/[Jj]et[Bb]rains/);
  });

  it("loads Satoshi font", () => {
    const content = readFile(PREVIEW_TS);
    expect(content).toMatch(/[Ss]atoshi/);
  });
});

// ===========================================================================
// 3. src/stories/DesignTokens.stories.tsx — Story file structure (AC2)
// ===========================================================================

describe("DesignTokens.stories.tsx — existence and Storybook structure", () => {
  it("file exists at src/stories/DesignTokens.stories.tsx", () => {
    expect(existsSync(DESIGN_TOKENS_STORY)).toBe(true);
  });

  it("has a default export (Storybook meta object)", () => {
    const content = readFile(DESIGN_TOKENS_STORY);
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readFile(DESIGN_TOKENS_STORY);
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readFile(DESIGN_TOKENS_STORY);
    // Named exports other than `default` are individual stories
    expect(content).toMatch(/export\s+const\s+\w+/);
  });

  it("shows color palette documentation (neutral, accent, or semantic tokens)", () => {
    const content = readFile(DESIGN_TOKENS_STORY);
    // Must reference at least one of the design system color token families
    const mentionsColors =
      /neutral|accent|success|warning|danger|info/.test(content);
    expect(mentionsColors).toBe(true);
  });

  it("shows typography scale documentation", () => {
    const content = readFile(DESIGN_TOKENS_STORY);
    // Must document type scale — font-size, heading, or typography
    const mentionsTypography =
      /font-size|typography|heading|typeScale|type-scale/i.test(content);
    expect(mentionsTypography).toBe(true);
  });

  it("shows spacing scale documentation", () => {
    const content = readFile(DESIGN_TOKENS_STORY);
    // Must document spacing tokens
    const mentionsSpacing = /spacing|space-|gap|padding/i.test(content);
    expect(mentionsSpacing).toBe(true);
  });
});

// ===========================================================================
// 4. package.json — Scripts (AC6)
// ===========================================================================

describe("package.json — storybook scripts", () => {
  it("has a `storybook` script", () => {
    const pkg = readPackageJson();
    expect(pkg.scripts).toBeDefined();
    expect(pkg.scripts!["storybook"]).toBeDefined();
  });

  it("`storybook` script runs `storybook dev`", () => {
    const pkg = readPackageJson();
    expect(pkg.scripts!["storybook"]).toMatch(/storybook\s+dev/);
  });

  it("`storybook` script uses port 6006", () => {
    const pkg = readPackageJson();
    expect(pkg.scripts!["storybook"]).toMatch(/-p\s*6006|--port\s*6006/);
  });

  it("has a `build-storybook` script", () => {
    const pkg = readPackageJson();
    expect(pkg.scripts!["build-storybook"]).toBeDefined();
  });

  it("`build-storybook` script runs `storybook build`", () => {
    const pkg = readPackageJson();
    expect(pkg.scripts!["build-storybook"]).toMatch(/storybook\s+build/);
  });
});

// ===========================================================================
// 5. package.json — Storybook devDependencies (AC1, AC6)
// ===========================================================================

describe("package.json — storybook devDependencies", () => {
  it("has @storybook/react-vite in devDependencies", () => {
    const pkg = readPackageJson();
    expect(pkg.devDependencies).toBeDefined();
    expect(pkg.devDependencies!["@storybook/react-vite"]).toBeDefined();
  });

  it("has storybook in devDependencies", () => {
    const pkg = readPackageJson();
    expect(pkg.devDependencies!["storybook"]).toBeDefined();
  });

  it("@storybook/react-vite version is 8.x or later", () => {
    const pkg = readPackageJson();
    const version = pkg.devDependencies!["@storybook/react-vite"] ?? "";
    // Accept ^8.x.x, ~8.x.x, 8.x.x, or >=8
    expect(version).toMatch(/^[\^~]?[89]|>=\s*[89]/);
  });

  it("storybook package version is 8.x or later", () => {
    const pkg = readPackageJson();
    const version = pkg.devDependencies!["storybook"] ?? "";
    expect(version).toMatch(/^[\^~]?[89]|>=\s*[89]/);
  });
});
