/**
 * Phase 4a: Automated validation tests for the @theme inline bridge.
 *
 * Group 1 — @theme inline completeness: verifies that all required design
 *   system tokens are mapped in the @theme inline block of globals.css.
 *
 * Group 2 — No broken class patterns: scans component .tsx files to ensure
 *   no legacy token-name-based Tailwind class patterns remain.
 *
 * Group 3 — Key Tailwind utilities exist: confirms that components have
 *   adopted the correct replacement utility patterns.
 */

import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { resolve, join } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const GLOBALS_PATH = resolve(__dirname, "..", "globals.css");

function readGlobals(): string {
  return readFileSync(GLOBALS_PATH, "utf-8");
}

/**
 * Extract the content of the @theme inline { ... } block.
 * Handles nested braces via a depth-counting walk.
 */
function extractThemeInlineBlock(css: string): string {
  const start = css.search(/@theme\s+inline\s*\{/);
  if (start === -1) return "";

  // Find the opening brace
  const braceStart = css.indexOf("{", start);
  let depth = 0;
  let i = braceStart;
  for (; i < css.length; i++) {
    if (css[i] === "{") depth++;
    else if (css[i] === "}") {
      depth--;
      if (depth === 0) break;
    }
  }
  return css.slice(braceStart + 1, i);
}

/**
 * Recursively collect all .tsx files under a directory.
 */
function collectTsxFiles(dir: string): string[] {
  const results: string[] = [];
  for (const entry of readdirSync(dir)) {
    const fullPath = join(dir, entry);
    const stat = statSync(fullPath);
    if (stat.isDirectory()) {
      results.push(...collectTsxFiles(fullPath));
    } else if (entry.endsWith(".tsx")) {
      results.push(fullPath);
    }
  }
  return results;
}

const COMPONENTS_UI_DIR     = resolve(__dirname, "../../components/ui");
const COMPONENTS_SHARED_DIR = resolve(__dirname, "../../components/shared");

function allComponentFiles(): string[] {
  return [
    ...collectTsxFiles(COMPONENTS_UI_DIR),
    ...collectTsxFiles(COMPONENTS_SHARED_DIR),
  ];
}

function readAllComponents(): string {
  return allComponentFiles()
    .map((f) => readFileSync(f, "utf-8"))
    .join("\n");
}

// ===========================================================================
// Group 1: @theme inline completeness
// ===========================================================================

describe("@theme inline completeness", () => {
  it("contains --spacing: 4px", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).toMatch(/--spacing\s*:\s*4px/);
  });

  it("contains all 8 font-size mappings: --text-2xs through --text-3xl", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    for (const size of ["2xs", "xs", "sm", "md", "lg", "xl", "2xl", "3xl"]) {
      expect(theme, `missing --text-${size}:`).toMatch(
        new RegExp(`--text-${size}\\s*:`)
      );
    }
  });

  it("contains --font-weight-medium:", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).toMatch(/--font-weight-medium\s*:/);
  });

  it("contains all 5 line-height mappings: --leading-tight through --leading-loose", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    for (const lh of ["tight", "snug", "normal", "relaxed", "loose"]) {
      expect(theme, `missing --leading-${lh}:`).toMatch(
        new RegExp(`--leading-${lh}\\s*:`)
      );
    }
  });

  it("contains --tracking-wide:", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).toMatch(/--tracking-wide\s*:/);
  });

  it("contains all 7 radius values + none: --radius-xs through --radius-full", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    for (const r of ["none", "xs", "sm", "md", "lg", "xl", "2xl", "full"]) {
      expect(theme, `missing --radius-${r}:`).toMatch(
        new RegExp(`--radius-${r}\\s*:`)
      );
    }
  });

  it("contains --shadow-raised:", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).toMatch(/--shadow-raised\s*:/);
  });

  it("contains --shadow-overlay:", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).toMatch(/--shadow-overlay\s*:/);
  });

  it("contains --ease-spring:", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).toMatch(/--ease-spring\s*:/);
  });

  it("contains --color-muted: (text color short alias)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).toMatch(/--color-muted\s*:/);
  });

  it("contains --color-heading:", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).toMatch(/--color-heading\s*:/);
  });

  it("contains --color-accent-9: (reference color scale)", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).toMatch(/--color-accent-9\s*:/);
  });

  it("contains --color-neutral-6:", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).toMatch(/--color-neutral-6\s*:/);
  });

  it("contains --color-danger-11:", () => {
    const theme = extractThemeInlineBlock(readGlobals());
    expect(theme).toMatch(/--color-danger-11\s*:/);
  });
});

// ===========================================================================
// Group 2: No broken class patterns in components
// ===========================================================================

describe("No broken class patterns in components", () => {
  it('has 0 occurrences of "text-font-size-" in component files', () => {
    const src = readAllComponents();
    const matches = src.match(/text-font-size-/g);
    expect(matches).toBeNull();
  });

  it('has 0 occurrences of "p-space-" in component files', () => {
    const src = readAllComponents();
    const matches = src.match(/p-space-/g);
    expect(matches).toBeNull();
  });

  it('has 0 occurrences of "gap-space-" in component files', () => {
    const src = readAllComponents();
    const matches = src.match(/gap-space-/g);
    expect(matches).toBeNull();
  });

  it('has 0 occurrences of "rounded-radius-" in component files', () => {
    const src = readAllComponents();
    const matches = src.match(/rounded-radius-/g);
    expect(matches).toBeNull();
  });

  it('has 0 occurrences of "h-control-height-" in component files', () => {
    const src = readAllComponents();
    const matches = src.match(/h-control-height-/g);
    expect(matches).toBeNull();
  });
});

// ===========================================================================
// Group 3: Key Tailwind utilities exist
// ===========================================================================

describe("Key Tailwind utilities exist in components", () => {
  it('at least one component file contains "text-sm"', () => {
    const files = allComponentFiles();
    const found = files.some((f) =>
      readFileSync(f, "utf-8").includes("text-sm")
    );
    expect(found).toBe(true);
  });

  it('at least one component file contains "p-4"', () => {
    const files = allComponentFiles();
    const found = files.some((f) =>
      readFileSync(f, "utf-8").includes("p-4")
    );
    expect(found).toBe(true);
  });

  it('at least one component file contains "rounded-md"', () => {
    const files = allComponentFiles();
    const found = files.some((f) =>
      readFileSync(f, "utf-8").includes("rounded-md")
    );
    expect(found).toBe(true);
  });
});
