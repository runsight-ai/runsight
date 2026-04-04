/**
 * RED-TEAM tests for RUN-368: Add API Key button replacing Run (no-key state).
 *
 * Acceptance Criteria:
 *   AC1: "Add API Key" shown when 0 providers
 *   AC2: "Run" shown when providers exist
 *   AC3: Button swap is reactive (provider query invalidation)
 *
 * These are source-reading tests that verify RunButton imports useProviders,
 * conditionally renders "Add API Key" vs "Run", and uses Button component.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SRC_DIR = resolve(__dirname, "../../..");

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

const RUN_BUTTON_PATH = "features/canvas/RunButton.tsx";

// ===========================================================================
// 1. RunButton imports useProviders (prerequisite for provider-aware logic)
// ===========================================================================

describe("RunButton imports useProviders (RUN-368)", () => {
  it("imports useProviders from queries/settings", () => {
    const source = readSource(RUN_BUTTON_PATH);
    expect(source).toMatch(/import.*useProviders.*from.*queries\/settings/);
  });
});

// ===========================================================================
// 2. Conditional rendering: "Add API Key" vs "Run" (AC1, AC2)
// ===========================================================================

describe("RunButton conditional rendering based on providers (RUN-368 AC1/AC2)", () => {
  it("renders 'Add API Key' text when no providers exist", () => {
    const source = readSource(RUN_BUTTON_PATH);
    expect(source).toMatch(/Add API Key/);
  });

  it("still renders 'Run' text when providers exist", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // "Run" label should still be present in the component for the has-providers state
    expect(source).toMatch(/Run/);
  });

  it("checks provider count to determine button mode", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Should derive a boolean from providers data length or similar
    const hasProviderCheck =
      /providers.*length|\.length\s*===\s*0|!providers|hasProviders|noProviders|hasKeys/.test(source);
    expect(
      hasProviderCheck,
      "Expected provider count check logic (e.g., providers.length === 0)",
    ).toBe(true);
  });

  it("uses Button component for the Add API Key state", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // The "Add API Key" text should be inside a <Button> element
    // Verify Button is used (already imported) and the text appears
    expect(source).toMatch(/<Button[\s\S]*?Add API Key/);
  });
});

// ===========================================================================
// 3. Button swap is reactive via useProviders query (AC3)
// ===========================================================================

describe("RunButton reactive provider check (RUN-368 AC3)", () => {
  it("calls useProviders hook (reactive via React Query)", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // useProviders() must be invoked (not just imported) for reactivity
    expect(source).toMatch(/useProviders\(\)/);
  });

  it("derives provider availability from useProviders data", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Should destructure or access .data from useProviders result
    expect(source).toMatch(/useProviders\(\)/) ;
    const accessesData = /providers|\.data/.test(source);
    expect(
      accessesData,
      "Expected useProviders result to be accessed for provider data",
    ).toBe(true);
  });
});

// ===========================================================================
// 4. Add API Key button uses a key icon
// ===========================================================================

describe("RunButton Add API Key styling (RUN-368)", () => {
  it("uses a key icon for the Add API Key state", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Should import a Key icon from lucide-react
    expect(source).toMatch(/Key/);
  });

  it("uses primary variant for Add API Key button", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // The "Add API Key" button should stand out as primary action
    expect(source).toMatch(/variant.*primary|"primary"/);
  });
});
