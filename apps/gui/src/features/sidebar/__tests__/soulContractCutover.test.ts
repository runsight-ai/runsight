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

  it("keeps the supported souls pages and palette files available", () => {
    expect(
      existsSync(resolve(SRC_DIR, "features/souls/SoulLibraryPage.tsx")),
      "Expected the supported souls library page to remain available",
    ).toBe(true);
    expect(
      existsSync(resolve(SRC_DIR, "features/souls/SoulFormPage.tsx")),
      "Expected the supported soul form page to remain available",
    ).toBe(true);
    expect(
      existsSync(resolve(SRC_DIR, "features/canvas/PaletteSidebar.tsx")),
      "Expected the supported canvas palette to remain available",
    ).toBe(true);
  });

  it("keeps the shared souls data-layer files available", () => {
    const routesSource = readSource("routes/index.tsx");

    expect(existsSync(resolve(SRC_DIR, "queries/souls.ts"))).toBe(true);
    expect(existsSync(resolve(SRC_DIR, "api/souls.ts"))).toBe(true);
    expect(routesSource).toMatch(/path:\s*"souls"/);
    expect(routesSource).toMatch(/path:\s*"souls\/new"/);
    expect(routesSource).toMatch(/path:\s*"souls\/:id\/edit"/);
  });
});
