import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const SRC_DIR = resolve(__dirname, "..", "..", "..");

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

describe("RUN-508 soul surface cleanup", () => {
  it("deletes the legacy sidebar soul modules", () => {
    expect(
      existsSync(resolve(SRC_DIR, "features/sidebar/SoulList.tsx")),
      "Expected SoulList.tsx to be removed with the retired sidebar island",
    ).toBe(false);
    expect(
      existsSync(resolve(SRC_DIR, "features/sidebar/SoulModals.tsx")),
      "Expected SoulModals.tsx to be removed with the retired sidebar island",
    ).toBe(false);
  });

  it("keeps the supported souls pages on the shared souls query layer", () => {
    const soulLibraryPageSource = readSource("features/souls/SoulLibraryPage.tsx");
    const soulFormPageSource = readSource("features/souls/SoulFormPage.tsx");
    const paletteSidebarSource = readSource("features/canvas/PaletteSidebar.tsx");

    expect(soulLibraryPageSource).toMatch(/@\/queries\/souls/);
    expect(soulFormPageSource).toMatch(/@\/queries\/souls/);
    expect(paletteSidebarSource).toMatch(/@\/queries\/souls/);
  });

  it("keeps the shared souls query and API adapters in place", () => {
    const soulsQuerySource = readSource("queries/souls.ts");
    const soulsApiSource = readSource("api/souls.ts");

    expect(soulsQuerySource).toMatch(/\.\.\/api\/souls/);
    expect(soulsApiSource.length).toBeGreaterThan(0);
  });
});
