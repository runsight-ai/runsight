/**
 * RED-TEAM tests for RUN-352: Redirect logic — / -> /setup/start when not onboarded.
 *
 * Source-reading pattern: verify structural properties by reading source files.
 *
 * Scope:
 *   - Route guard using React Router `loader` on the ShellLayout route
 *   - Uses queryClient.fetchQuery with staleTime: 30_000
 *   - If onboarding_completed === false -> redirect('/setup/start')
 *   - If settings fetch fails or returns a malformed payload -> fail closed to
 *     a dedicated routed unavailable state
 *   - Reverse guard on /setup/start: if onboarding_completed === true -> redirect('/')
 *
 * AC:
 *   AC1: First visit (no settings) redirects to /setup/start
 *   AC2: After completing setup, / shows dashboard
 *   AC3: Direct URL to /setup/start after onboarding -> reverse guard redirects to /
 *   AC4: No flash of dashboard content before redirect
 *
 * Expected failures (current state):
 *   - routes/guards.ts does not exist
 *   - routes/index.tsx has no loader on ShellLayout route
 *   - routes/index.tsx has no loader on /setup/start route
 */

import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SRC_DIR = resolve(__dirname, "../..");

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

function fileExists(relativePath: string): boolean {
  return existsSync(resolve(SRC_DIR, relativePath));
}

// ---------------------------------------------------------------------------
// File paths
// ---------------------------------------------------------------------------

const GUARDS_PATH = "routes/guards.ts";
const ROUTES_PATH = "routes/index.tsx";

// ===========================================================================
// 1. Guards file exists and exports factory functions
// ===========================================================================

describe("Guards file exists and exports factory functions", () => {
  it("routes/guards.ts exists on disk", () => {
    expect(
      fileExists(GUARDS_PATH),
      "Expected routes/guards.ts to exist",
    ).toBe(true);
  });

  it("exports createSetupGuardLoader", () => {
    const source = readSource(GUARDS_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+createSetupGuardLoader/);
  });

  it("exports createReverseGuardLoader", () => {
    const source = readSource(GUARDS_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+createReverseGuardLoader/);
  });
});

// ===========================================================================
// 2. ShellLayout route has a loader (AC4 — no flash)
// ===========================================================================

describe("ShellLayout route has a loader property", () => {
  it("routes/index.tsx imports guards", () => {
    const source = readSource(ROUTES_PATH);
    expect(source).toMatch(/import.*from.*["']\.\/guards["']/);
  });

  it("ShellLayout route definition includes a loader property", () => {
    const source = readSource(ROUTES_PATH);
    // The ShellLayout route object should have a `loader` key.
    // The route is defined with `element: <ShellLayout />` — we look for
    // `loader` appearing in the same route object (before `children`).
    // Check that loader appears near the ShellLayout element in the route definition
    const hasLoaderNearShell =
      /loader\s*:[\s\S]*?element:\s*<ShellLayout|element:\s*<ShellLayout[\s\S]*?loader\s*:/.test(
        source,
      );
    expect(
      hasLoaderNearShell,
      "Expected a `loader` property on the ShellLayout route object",
    ).toBe(true);
  });

  it("ShellLayout loader uses createSetupGuardLoader", () => {
    const source = readSource(ROUTES_PATH);
    expect(source).toMatch(/createSetupGuardLoader/);
  });
});

// ===========================================================================
// 3. /setup/start route has a reverse guard loader (AC3)
// ===========================================================================

describe("/setup/start route has a reverse guard loader", () => {
  it("setup/start route definition includes a loader property", () => {
    const source = readSource(ROUTES_PATH);
    // Look for loader near the setup/start path definition
    const hasLoaderNearSetup =
      /loader\s*:[\s\S]{0,200}?setup\/start|setup\/start[\s\S]{0,200}?loader\s*:/.test(
        source,
      );
    expect(
      hasLoaderNearSetup,
      "Expected a `loader` property on the /setup/start route",
    ).toBe(true);
  });

  it("setup/start loader uses createReverseGuardLoader", () => {
    const source = readSource(ROUTES_PATH);
    expect(source).toMatch(/createReverseGuardLoader/);
  });
});

// ===========================================================================
// 4. Guard reads onboarding_completed from app settings (AC1, AC2)
// ===========================================================================

describe("Guard reads onboarding_completed from app settings", () => {
  it("guards.ts imports queryKeys or uses settings query key", () => {
    const source = readSource(GUARDS_PATH);
    const usesSettingsKey =
      /queryKeys\.settings\.appSettings|["']settings["'].*["']appSettings["']/.test(
        source,
      );
    expect(
      usesSettingsKey,
      "Expected guard to reference app settings query key",
    ).toBe(true);
  });

  it("guards.ts uses fetchQuery to read settings", () => {
    const source = readSource(GUARDS_PATH);
    expect(source).toMatch(/fetchQuery/);
  });

  it("guards.ts uses staleTime on the fetchQuery call", () => {
    const source = readSource(GUARDS_PATH);
    const hasStaleTime = /staleTime\s*:\s*\d+/.test(source);
    expect(
      hasStaleTime,
      "Expected staleTime on the fetchQuery call",
    ).toBe(true);
  });

  it("guards.ts reads onboarding_completed from the fetched settings", () => {
    const source = readSource(GUARDS_PATH);
    expect(source).toMatch(/onboarding_completed/);
  });
});

// ===========================================================================
// 5. Guard redirects to /setup/start when not onboarded (AC1)
// ===========================================================================

describe("Guard redirects to /setup/start when not onboarded (AC1)", () => {
  it("guards.ts imports redirect from react-router", () => {
    const source = readSource(GUARDS_PATH);
    expect(source).toMatch(/import.*redirect.*from.*["']react-router["']/);
  });

  it("guard throws redirect to /setup/start when onboarding_completed is false", () => {
    const source = readSource(GUARDS_PATH);
    // Should throw redirect('/setup/start') when onboarding not completed
    const hasRedirectToSetup =
      /redirect\s*\(\s*["']\/setup\/start["']\s*\)/.test(source);
    expect(
      hasRedirectToSetup,
      "Expected redirect('/setup/start') in guard logic",
    ).toBe(true);
  });

  it("guard redirects to setup only when onboarding_completed is explicitly false", () => {
    const source = readSource(GUARDS_PATH);
    const checksExplicitFalse = /onboarding_completed\s*===\s*false/.test(source);
    expect(
      checksExplicitFalse,
      "Expected guard to redirect to setup only when onboarding_completed is explicitly false",
    ).toBe(true);

    expect(
      source,
      "Expected guard to avoid a falsy onboarding check that treats malformed payloads as setup-ready",
    ).not.toMatch(/!\s*settings\.onboarding_completed/);
  });
});

// ===========================================================================
// 6. Guard allows through when onboarding is completed (AC2)
// ===========================================================================

describe("Guard allows through when onboarding is completed (AC2)", () => {
  it("guard returns null when onboarding_completed is true", () => {
    const source = readSource(GUARDS_PATH);
    // When onboarding is complete, the loader should return null (no redirect).
    // This is the standard React Router pattern for "do nothing" in a loader.
    expect(source).toMatch(/return\s+null/);
  });
});

// ===========================================================================
// 7. Reverse guard redirects to / when already onboarded (AC3)
// ===========================================================================

describe("Reverse guard redirects to / when already onboarded (AC3)", () => {
  it("reverse guard throws redirect to / when onboarding_completed is true", () => {
    const source = readSource(GUARDS_PATH);
    // Should redirect to root when already onboarded
    const hasRedirectToRoot =
      /redirect\s*\(\s*["']\/["']\s*\)/.test(source);
    expect(
      hasRedirectToRoot,
      "Expected redirect('/') in reverse guard logic",
    ).toBe(true);
  });

  it("reverse guard allows through when onboarding_completed is false", () => {
    const source = readSource(GUARDS_PATH);
    // Both guards should have return null — the reverse guard returns null
    // when onboarding is NOT completed (user should stay on /setup/start)
    const nullReturns = (source.match(/return\s+null/g) ?? []).length;
    expect(
      nullReturns,
      "Expected at least 2 return null statements (one per guard)",
    ).toBeGreaterThanOrEqual(2);
  });
});

// ===========================================================================
// 8. Fail-closed routing for unavailable settings
// ===========================================================================

describe("Fail-closed routing when settings are unavailable", () => {
  it("guard has try/catch around the fetch", () => {
    const source = readSource(GUARDS_PATH);
    expect(source).toMatch(/try\s*\{/);
    expect(source).toMatch(/catch/);
  });

  it("catch blocks redirect to a dedicated /setup/unavailable route", () => {
    const source = readSource(GUARDS_PATH);
    const catchBlocks = source.match(/catch[\s\S]*?\{([\s\S]*?)\}/g) ?? [];

    expect(
      catchBlocks.length,
      "Expected both setup and reverse guards to wrap fetch failures in catch blocks",
    ).toBeGreaterThanOrEqual(2);

    for (const catchBlock of catchBlocks) {
      expect(catchBlock).toMatch(/redirect\s*\(\s*["']\/setup\/unavailable["']\s*\)/);
      expect(catchBlock).not.toMatch(/return\s+null/);
    }
  });

  it("routes/index.tsx declares a dedicated /setup/unavailable route", () => {
    const source = readSource(ROUTES_PATH);
    expect(source).toMatch(/path:\s*["']setup\/unavailable["']/);
  });
});

// ===========================================================================
// 9. Guard accepts QueryClient parameter (factory pattern)
// ===========================================================================

describe("Guard factory accepts QueryClient parameter", () => {
  it("createSetupGuardLoader accepts queryClient parameter", () => {
    const source = readSource(GUARDS_PATH);
    // Factory function should accept queryClient as argument
    const hasQueryClientParam =
      /createSetupGuardLoader\s*\(\s*queryClient/.test(source);
    expect(
      hasQueryClientParam,
      "Expected createSetupGuardLoader to accept queryClient parameter",
    ).toBe(true);
  });

  it("createReverseGuardLoader accepts queryClient parameter", () => {
    const source = readSource(GUARDS_PATH);
    const hasQueryClientParam =
      /createReverseGuardLoader\s*\(\s*queryClient/.test(source);
    expect(
      hasQueryClientParam,
      "Expected createReverseGuardLoader to accept queryClient parameter",
    ).toBe(true);
  });

  it("guards.ts imports settingsApi or uses settings query function", () => {
    const source = readSource(GUARDS_PATH);
    // The guard needs the actual fetch function to pass to fetchQuery
    const usesSettingsApi =
      /settingsApi\.getAppSettings|settingsApi|getAppSettings/.test(source);
    expect(
      usesSettingsApi,
      "Expected guard to use settingsApi for the fetch function",
    ).toBe(true);
  });
});
