import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const SRC_DIR = resolve(__dirname, "..", "..");

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

describe("RUN-508 legacy sidebar CRUD cleanup", () => {
  it.each([
    "features/sidebar/SoulList.tsx",
    "features/sidebar/SoulModals.tsx",
    "features/sidebar/TaskModals.tsx",
    "features/sidebar/StepModals.tsx",
    "api/tasks.ts",
    "api/steps.ts",
    "queries/tasks.ts",
    "queries/steps.ts",
  ])("%s is deleted from the GUI source tree", (relativePath) => {
    expect(
      existsSync(resolve(SRC_DIR, relativePath)),
      `Expected ${relativePath} to be removed with the retired sidebar CRUD island`,
    ).toBe(false);
  });

  it("does not leave /tasks or /steps in the shipped router", () => {
    const routesSource = readSource("routes/index.tsx");

    expect(routesSource).not.toMatch(/path:\s*"tasks"/);
    expect(routesSource).not.toMatch(/path:\s*"steps"/);
    expect(routesSource).not.toMatch(/features\/sidebar\/(?:SoulList|TaskList|StepList)/);
  });

  it("keeps the supported souls routes and shared files available", () => {
    const routesSource = readSource("routes/index.tsx");

    expect(routesSource).toMatch(/path:\s*"souls"/);
    expect(routesSource).toMatch(/path:\s*"souls\/new"/);
    expect(routesSource).toMatch(/path:\s*"souls\/:id\/edit"/);

    expect(existsSync(resolve(SRC_DIR, "features/souls/SoulLibraryPage.tsx"))).toBe(true);
    expect(existsSync(resolve(SRC_DIR, "features/souls/SoulFormPage.tsx"))).toBe(true);
    expect(existsSync(resolve(SRC_DIR, "features/surface/PaletteSidebar.tsx"))).toBe(true);
    expect(existsSync(resolve(SRC_DIR, "queries/souls.ts"))).toBe(true);
    expect(existsSync(resolve(SRC_DIR, "api/souls.ts"))).toBe(true);
  });

  it("cleans stale test-suite references to the retired sidebar island", () => {
    const toastNotificationsSource = readSource("queries/__tests__/toastNotifications.test.ts");
    const screenTokenSweepSource = readSource("features/__tests__/screenTokenSweep.test.ts");
    const legacyRouteCleanupSource = readSource("routes/__tests__/run431LegacyRouteCleanup.test.ts");

    expect(toastNotificationsSource).not.toMatch(/queries\/tasks\.ts|queries\/steps\.ts/);
    expect(legacyRouteCleanupSource).not.toMatch(/features\/sidebar\/(?:SoulList|TaskList|StepList)/);
    expect(legacyRouteCleanupSource).not.toMatch(/vi\.mock\("@\/features\/sidebar\//);

    expect(screenTokenSweepSource).not.toMatch(/const SIDEBAR_FEATURES\s*=/);
    expect(screenTokenSweepSource).not.toMatch(/for\s*\(const filePath of SIDEBAR_FEATURES\)/);
  });
});
