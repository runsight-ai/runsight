/**
 * RED-TEAM tests for RUN-350: Delete LandingPage + OnboardingWizard + stale routes.
 *
 * After this cleanup the old onboarding surfaces are gone:
 *   - features/landing/LandingPage.tsx           (deleted)
 *   - features/onboarding/OnboardingWizard.tsx    (deleted)
 *   - features/templates/TemplatesPage.tsx         (deleted)
 *   - Routes /landing, /onboarding, /templates     (removed from router)
 *
 * Kept intact:
 *   - components/provider/ProviderSetup.tsx        (reused in API key modal)
 *   - features/settings/AddProviderDialog.tsx      (serves Settings page)
 *   - queries/settings.ts                          (provider CRUD queries)
 *
 * Expected failures (current state):
 *   - All three files still exist on disk
 *   - routes/index.tsx still defines /landing, /onboarding, /templates
 *   - routes/index.tsx still imports the deleted modules
 *   - screenTokenSweep.test.ts still lists the deleted files
 */

import { describe, it, expect } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SRC_DIR = resolve(__dirname, "../..");

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

// ---------------------------------------------------------------------------
// 1. Deleted files must NOT exist on disk
// ---------------------------------------------------------------------------

describe("Deleted page component files are removed from disk", () => {
  it("features/landing/LandingPage.tsx does NOT exist", () => {
    const filePath = resolve(SRC_DIR, "features/landing/LandingPage.tsx");
    expect(existsSync(filePath), `Expected ${filePath} to be deleted`).toBe(false);
  });

  it("features/onboarding/OnboardingWizard.tsx does NOT exist", () => {
    const filePath = resolve(SRC_DIR, "features/onboarding/OnboardingWizard.tsx");
    expect(existsSync(filePath), `Expected ${filePath} to be deleted`).toBe(false);
  });

  it("features/templates/TemplatesPage.tsx does NOT exist", () => {
    const filePath = resolve(SRC_DIR, "features/templates/TemplatesPage.tsx");
    expect(existsSync(filePath), `Expected ${filePath} to be deleted`).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 2. Kept files MUST still exist on disk
// ---------------------------------------------------------------------------

describe("Kept files still exist", () => {
  it("components/provider/ProviderSetup.tsx still exists", () => {
    const filePath = resolve(SRC_DIR, "components/provider/ProviderSetup.tsx");
    expect(existsSync(filePath), `Expected ${filePath} to still exist`).toBe(true);
  });

  it("features/settings/AddProviderDialog.tsx still exists", () => {
    const filePath = resolve(SRC_DIR, "features/settings/AddProviderDialog.tsx");
    expect(existsSync(filePath), `Expected ${filePath} to still exist`).toBe(true);
  });

  it("queries/settings.ts still exists", () => {
    const filePath = resolve(SRC_DIR, "queries/settings.ts");
    expect(existsSync(filePath), `Expected ${filePath} to still exist`).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 3. Router config must NOT contain deleted routes
// ---------------------------------------------------------------------------

describe("Router config has no deleted routes", () => {
  let routerSource: string;

  it("routes/index.tsx does NOT define a /landing route", () => {
    routerSource = readSource("routes/index.tsx");
    // Match the route path definition: path: "landing" or path: "/landing"
    expect(routerSource).not.toMatch(/path:\s*["']\/?\blanding\b["']/);
  });

  it("routes/index.tsx does NOT define an /onboarding route", () => {
    routerSource = readSource("routes/index.tsx");
    expect(routerSource).not.toMatch(/path:\s*["']\/?\bonboarding\b["']/);
  });

  it("routes/index.tsx does NOT define a /templates route", () => {
    routerSource = readSource("routes/index.tsx");
    expect(routerSource).not.toMatch(/path:\s*["']\/?\btemplates\b["']/);
  });
});

// ---------------------------------------------------------------------------
// 4. No dead imports — router must NOT reference deleted modules
// ---------------------------------------------------------------------------

describe("No dead imports referencing deleted modules", () => {
  let routerSource: string;

  it("routes/index.tsx does NOT import LandingPage", () => {
    routerSource = readSource("routes/index.tsx");
    expect(routerSource).not.toMatch(/features\/landing\/LandingPage/);
  });

  it("routes/index.tsx does NOT import OnboardingWizard", () => {
    routerSource = readSource("routes/index.tsx");
    expect(routerSource).not.toMatch(/features\/onboarding\/OnboardingWizard/);
  });

  it("routes/index.tsx does NOT import TemplatesPage", () => {
    routerSource = readSource("routes/index.tsx");
    expect(routerSource).not.toMatch(/features\/templates\/TemplatesPage/);
  });
});

// ---------------------------------------------------------------------------
// 5. No stale references in other test files
// ---------------------------------------------------------------------------

describe("No stale references in screenTokenSweep", () => {
  it("screenTokenSweep.test.ts does NOT reference LandingPage.tsx", () => {
    const source = readSource("features/__tests__/screenTokenSweep.test.ts");
    expect(source).not.toMatch(/LandingPage\.tsx/);
  });

  it("screenTokenSweep.test.ts does NOT reference OnboardingWizard.tsx", () => {
    const source = readSource("features/__tests__/screenTokenSweep.test.ts");
    expect(source).not.toMatch(/OnboardingWizard\.tsx/);
  });

  it("screenTokenSweep.test.ts does NOT reference TemplatesPage.tsx", () => {
    const source = readSource("features/__tests__/screenTokenSweep.test.ts");
    expect(source).not.toMatch(/TemplatesPage\.tsx/);
  });
});

// ---------------------------------------------------------------------------
// 6. Router still has the catch-all redirect (404 -> /)
// ---------------------------------------------------------------------------

describe("Catch-all route still redirects to /", () => {
  it("routes/index.tsx still has a wildcard catch-all with Navigate to '/'", () => {
    const routerSource = readSource("routes/index.tsx");
    // Should still have: { path: "*", element: <Navigate to="/" replace /> }
    expect(routerSource).toMatch(/path:\s*["']\*["']/);
    expect(routerSource).toMatch(/Navigate\s+to=["']\/["']/);
  });
});
