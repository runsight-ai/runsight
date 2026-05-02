/**
 * Smoke coverage for the @theme inline bridge.
 *
 * Governance: verifies the stable Tailwind-facing token API exposed by
 * globals.css without scanning component source for migration details.
 * Owner: packages/ui style-system maintainers.
 * Boundary: packages/ui/src/styles/globals.css @theme inline block only.
 * Exit criteria: remove this once Tailwind token generation has a dedicated
 * typed manifest test.
 */

import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const GLOBALS_PATH = resolve(dirname(fileURLToPath(import.meta.url)), "..", "globals.css");

function readGlobals(): string {
  return readFileSync(GLOBALS_PATH, "utf-8");
}

function extractThemeInlineBlock(css: string): string {
  const start = css.search(/@theme\s+inline\s*\{/);
  expect(start).toBeGreaterThanOrEqual(0);

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

const THEME_BRIDGE_TOKENS = [
  "--spacing",
  "--text-sm",
  "--font-weight-medium",
  "--radius-md",
  "--shadow-raised",
  "--shadow-overlay",
  "--color-surface-primary",
  "--color-border-default",
  "--color-interactive-default",
  "--color-heading",
] as const;

describe("@theme inline bridge smoke", () => {
  it("exposes durable Tailwind token mappings", () => {
    const theme = extractThemeInlineBlock(readGlobals());

    for (const token of THEME_BRIDGE_TOKENS) {
      expect(theme).toMatch(new RegExp(`${token}\\s*:`));
    }
  });

  it("keeps spacing and radius bridge values stable for utility generation", () => {
    const theme = extractThemeInlineBlock(readGlobals());

    expect(theme).toMatch(/--spacing\s*:\s*4px/);
    expect(theme).toMatch(/--radius-md\s*:\s*4px/);
  });
});
