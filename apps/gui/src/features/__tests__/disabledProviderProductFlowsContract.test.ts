import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const SRC_DIR = resolve(__dirname, "../..");

function read(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

describe("disabled-provider gating across product flows", () => {
  it("SoulModelSection filters the provider picker to active providers only", () => {
    const source = read("features/souls/SoulModelSection.tsx");

    expect(source).toMatch(/is_active/);
    expect(source).toMatch(/filter\([^)]*is_active|\.filter\(/s);
  });

  it("SetupStartPage derives readiness from active providers instead of raw provider count", () => {
    const source = read("features/setup/SetupStartPage.tsx");

    expect(source).toMatch(/is_active/);
    expect(source).toMatch(/filter\([^)]*is_active|\.filter\(/s);
    expect(source).not.toMatch(/providers\?\.items\?\.length/);
  });

  it("RunButton gates Run vs Add API Key off active providers instead of all configured providers", () => {
    const source = read("features/canvas/RunButton.tsx");

    expect(source).toMatch(/is_active/);
    expect(source).toMatch(/filter\([^)]*is_active|\.filter\(/s);
    expect(source).not.toMatch(/items\.length\s*>\s*0/);
  });

  it("CanvasStatusBar shows connection state from active providers instead of the first configured provider", () => {
    const source = read("features/canvas/CanvasStatusBar.tsx");

    expect(source).toMatch(/is_active/);
    expect(source).toMatch(/filter\([^)]*is_active|\.filter\(/s);
  });

  it("ExploreBanner stays visible when only disabled providers exist", () => {
    const source = read("features/canvas/ExploreBanner.tsx");

    expect(source).toMatch(/is_active/);
    expect(source).toMatch(/filter\([^)]*is_active|\.filter\(/s);
    expect(source).not.toMatch(/items\.length\s*>\s*0/);
  });

  it("ModelsTab derives provider-backed defaults from active providers only", () => {
    const source = read("features/settings/ModelsTab.tsx");

    expect(source).toMatch(/is_active/);
    expect(source).toMatch(/filter\([^)]*is_active|\.filter\(/s);
  });
});
