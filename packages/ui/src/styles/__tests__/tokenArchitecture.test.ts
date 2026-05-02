/**
 * Token architecture smoke coverage for globals.css.
 *
 * Governance: stable style-system coverage for design tokens and the global
 * CSS contracts that package consumers rely on.
 * Owner: packages/ui design-system maintainers.
 * Boundary: durable token architecture in packages/ui/src/styles/globals.css;
 * migration sweeps and component token scans belong elsewhere.
 * Exit criteria: replace with generated token manifest checks when the design
 * token source of truth is promoted.
 */

import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const GLOBALS_PATH = resolve(dirname(fileURLToPath(import.meta.url)), "..", "globals.css");

function readGlobals(): string {
  return readFileSync(GLOBALS_PATH, "utf-8");
}

function extractBlock(css: string, selector: string): string {
  const start = css.indexOf(selector);
  expect(start, `Expected ${selector} block`).toBeGreaterThanOrEqual(0);

  const braceStart = css.indexOf("{", start);
  let depth = 0;

  for (let i = braceStart; i < css.length; i += 1) {
    if (css[i] === "{") {
      depth += 1;
    } else if (css[i] === "}") {
      depth -= 1;
      if (depth === 0) {
        return css.slice(braceStart + 1, i);
      }
    }
  }

  return "";
}

function cssProperty(name: string): RegExp {
  return new RegExp(`${name}\\s*:`);
}

const ROOT_SYSTEM_TOKENS = [
  "--font-body",
  "--font-mono",
  "--surface-primary",
  "--surface-overlay",
  "--text-primary",
  "--text-on-accent",
  "--border-default",
  "--border-focus",
  "--interactive-default",
  "--elevation-overlay-shadow",
  "--focus-ring-color",
] as const;

const THEME_API_TOKENS = [
  "--color-surface-primary",
  "--color-surface-overlay",
  "--color-border-default",
  "--color-interactive-default",
  "--color-heading",
  "--radius-md",
  "--spacing",
  "--shadow-overlay",
] as const;

describe("token architecture smoke", () => {
  it("retains required stylesheet imports", () => {
    const css = readGlobals();

    for (const imported of ["tailwindcss", "tw-animate-css", "shadcn/tailwind.css"]) {
      expect(css).toMatch(new RegExp(`@import\\s+["']${imported}["']`));
    }
  });

  it("defines durable root system tokens", () => {
    const root = extractBlock(readGlobals(), ":root");

    for (const token of ROOT_SYSTEM_TOKENS) {
      expect(root).toMatch(cssProperty(token));
    }
  });

  it("bridges durable token APIs through @theme inline", () => {
    const theme = extractBlock(readGlobals(), "@theme inline");

    for (const token of THEME_API_TOKENS) {
      expect(theme).toMatch(cssProperty(token));
    }
  });
});
