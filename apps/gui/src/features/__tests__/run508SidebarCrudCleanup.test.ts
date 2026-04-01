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

  it("keeps the supported souls library and palette wired to the shared souls hooks", () => {
    const soulLibraryPageSource = readSource("features/souls/SoulLibraryPage.tsx");
    const soulFormPageSource = readSource("features/souls/SoulFormPage.tsx");
    const paletteSidebarSource = readSource("features/canvas/PaletteSidebar.tsx");
    const soulsQuerySource = readSource("queries/souls.ts");
    const soulsApiSource = readSource("api/souls.ts");

    expect(soulLibraryPageSource).toMatch(/@\/queries\/souls/);
    expect(soulFormPageSource).toMatch(/@\/queries\/souls/);
    expect(paletteSidebarSource).toMatch(/@\/queries\/souls/);
    expect(soulsQuerySource).toMatch(/\.\.\/api\/souls/);
    expect(soulsApiSource.length).toBeGreaterThan(0);
  });
});
