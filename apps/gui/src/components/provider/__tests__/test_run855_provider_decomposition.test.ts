/**
 * RED-TEAM tests for RUN-855: Decompose oversized ProviderSetup component.
 *
 * Source-reading pattern: verify structural properties by reading source files.
 *
 * AC1: ProviderSetup decomposed — wizard steps as sub-components, form state in
 *      custom hook, API calls in custom hook
 * AC3: Each sub-component ≤80 lines of logic
 * AC4: All existing tests still pass (behavioral: ProviderSetup still exported)
 *
 * Expected failures (current state):
 *   - useProviderSetupForm hook does not exist
 *   - useProviderConnection hook does not exist
 *   - ProviderSetup.tsx exceeds 80 lines
 *   - ProviderSetup.tsx contains more than 5 useState calls
 */

import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const PROVIDER_DIR = resolve(__dirname, "..");
const HOOKS_DIR = resolve(PROVIDER_DIR, "hooks");

function readSource(filePath: string): string {
  return readFileSync(filePath, "utf-8");
}

function fileExists(filePath: string): boolean {
  return existsSync(filePath);
}

function countLines(source: string): number {
  // Count non-empty, non-comment-only lines
  return source
    .split("\n")
    .filter((line) => line.trim().length > 0)
    .length;
}

function countUseState(source: string): number {
  return (source.match(/\buseState\s*</g) || []).length;
}

// ---------------------------------------------------------------------------
// File paths
// ---------------------------------------------------------------------------

const PROVIDER_SETUP_PATH = resolve(PROVIDER_DIR, "ProviderSetup.tsx");
const FORM_HOOK_PATH = resolve(HOOKS_DIR, "useProviderSetupForm.ts");
const CONNECTION_HOOK_PATH = resolve(HOOKS_DIR, "useProviderConnection.ts");

// ===========================================================================
// 1. New hook files exist (AC1)
// ===========================================================================

describe("New hook files exist (AC1)", () => {
  it("hooks/useProviderSetupForm.ts exists", () => {
    expect(
      fileExists(FORM_HOOK_PATH),
      "Expected components/provider/hooks/useProviderSetupForm.ts to exist",
    ).toBe(true);
  });

  it("hooks/useProviderConnection.ts exists", () => {
    expect(
      fileExists(CONNECTION_HOOK_PATH),
      "Expected components/provider/hooks/useProviderConnection.ts to exist",
    ).toBe(true);
  });
});

// ===========================================================================
// 2. useProviderSetupForm hook structure (AC1 — form state in custom hook)
// ===========================================================================

describe("useProviderSetupForm hook structure (AC1)", () => {
  it("exports useProviderSetupForm function", () => {
    const source = readSource(FORM_HOOK_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+useProviderSetupForm/);
  });

  it("manages selectedProviderId state", () => {
    const source = readSource(FORM_HOOK_PATH);
    expect(source).toMatch(/selectedProviderId/);
  });

  it("manages apiKey state", () => {
    const source = readSource(FORM_HOOK_PATH);
    expect(source).toMatch(/apiKey/);
  });

  it("manages displayName state", () => {
    const source = readSource(FORM_HOOK_PATH);
    expect(source).toMatch(/displayName/);
  });

  it("manages useEnvVar state", () => {
    const source = readSource(FORM_HOOK_PATH);
    expect(source).toMatch(/useEnvVar/);
  });

  it("exposes selectProvider action", () => {
    const source = readSource(FORM_HOOK_PATH);
    expect(source).toMatch(/selectProvider/);
  });

  it("exposes reset or fullReset function", () => {
    const source = readSource(FORM_HOOK_PATH);
    expect(source).toMatch(/reset|fullReset/);
  });

  it("is ≤80 non-empty lines", () => {
    const source = readSource(FORM_HOOK_PATH);
    const lines = countLines(source);
    expect(lines, `useProviderSetupForm.ts has ${lines} non-empty lines, expected ≤80`).toBeLessThanOrEqual(80);
  });
});

// ===========================================================================
// 3. useProviderConnection hook structure (AC1 — API calls in custom hook)
// ===========================================================================

describe("useProviderConnection hook structure (AC1)", () => {
  it("exports useProviderConnection function", () => {
    const source = readSource(CONNECTION_HOOK_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+useProviderConnection/);
  });

  it("imports useCreateProvider from queries/settings", () => {
    const source = readSource(CONNECTION_HOOK_PATH);
    expect(source).toMatch(/useCreateProvider/);
  });

  it("imports useUpdateProvider from queries/settings", () => {
    const source = readSource(CONNECTION_HOOK_PATH);
    expect(source).toMatch(/useUpdateProvider/);
  });

  it("imports useTestProviderConnection from queries/settings", () => {
    const source = readSource(CONNECTION_HOOK_PATH);
    expect(source).toMatch(/useTestProviderConnection/);
  });

  it("manages testStatus state", () => {
    const source = readSource(CONNECTION_HOOK_PATH);
    expect(source).toMatch(/testStatus/);
  });

  it("manages testMessage state", () => {
    const source = readSource(CONNECTION_HOOK_PATH);
    expect(source).toMatch(/testMessage/);
  });

  it("exposes runTest function", () => {
    const source = readSource(CONNECTION_HOOK_PATH);
    expect(source).toMatch(/runTest/);
  });

  it("is ≤80 non-empty lines", () => {
    const source = readSource(CONNECTION_HOOK_PATH);
    const lines = countLines(source);
    expect(lines, `useProviderConnection.ts has ${lines} non-empty lines, expected ≤80`).toBeLessThanOrEqual(80);
  });
});

// ===========================================================================
// 4. ProviderSetup main component line count (AC3)
// ===========================================================================

describe("ProviderSetup main component ≤80 lines (AC3)", () => {
  it("ProviderSetup.tsx has ≤80 non-empty lines after decomposition", () => {
    const source = readSource(PROVIDER_SETUP_PATH);
    const lines = countLines(source);
    expect(lines, `ProviderSetup.tsx has ${lines} non-empty lines, expected ≤80`).toBeLessThanOrEqual(80);
  });
});

// ===========================================================================
// 5. ProviderSetup useState count (AC1 — form state extracted)
// ===========================================================================

describe("ProviderSetup main component has ≤5 useState calls (AC1)", () => {
  it("ProviderSetup.tsx uses ≤5 useState calls in main component", () => {
    const source = readSource(PROVIDER_SETUP_PATH);
    const count = countUseState(source);
    expect(count, `ProviderSetup.tsx has ${count} useState calls, expected ≤5`).toBeLessThanOrEqual(5);
  });
});

// ===========================================================================
// 6. ProviderSetup still exported (AC4 — behavioral continuity)
// ===========================================================================

describe("ProviderSetup still exported (AC4)", () => {
  it("ProviderSetup is still exported from ProviderSetup.tsx", () => {
    const source = readSource(PROVIDER_SETUP_PATH);
    expect(source).toMatch(/export.*ProviderSetup/);
  });

  it("ProviderSetup uses custom hooks (imports from hooks/)", () => {
    const source = readSource(PROVIDER_SETUP_PATH);
    expect(source).toMatch(/hooks\/useProviderSetupForm|\.\/hooks\//);
  });

  it("ProviderDef and TestStatus types still exported", () => {
    const source = readSource(PROVIDER_SETUP_PATH);
    expect(source).toMatch(/export.*ProviderDef/);
    expect(source).toMatch(/export.*TestStatus/);
  });

  it("HERO_PROVIDERS and ALL_PROVIDERS still exported", () => {
    const source = readSource(PROVIDER_SETUP_PATH);
    expect(source).toMatch(/export.*HERO_PROVIDERS/);
    expect(source).toMatch(/export.*ALL_PROVIDERS/);
  });
});

// ===========================================================================
// 7. Hook files have correct TypeScript structure
// ===========================================================================

describe("Hook files have correct TypeScript structure", () => {
  it("useProviderSetupForm returns an object (not void)", () => {
    const source = readSource(FORM_HOOK_PATH);
    // Should return an object with multiple fields
    expect(source).toMatch(/return\s*\{/);
  });

  it("useProviderConnection returns an object (not void)", () => {
    const source = readSource(CONNECTION_HOOK_PATH);
    expect(source).toMatch(/return\s*\{/);
  });

  it("useProviderSetupForm imports useState from react", () => {
    const source = readSource(FORM_HOOK_PATH);
    expect(source).toMatch(/import.*useState.*from.*react/);
  });
});
