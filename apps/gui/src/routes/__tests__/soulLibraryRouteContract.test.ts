import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const SRC_DIR = resolve(__dirname, "../..");
const ROUTES_PATH = resolve(SRC_DIR, "routes/index.tsx");

function readRoutes(): string {
  return readFileSync(ROUTES_PATH, "utf-8");
}

describe("RUN-452 route wiring", () => {
  it("routes /souls to SoulLibraryPage instead of the legacy SoulList", () => {
    const source = readRoutes();

    expect(source).toMatch(/path:\s*["']souls["']/);
    expect(source).toMatch(/SoulLibraryPage/);
    expect(source).not.toMatch(/features\/sidebar\/SoulList/);
    expect(source).not.toMatch(/CrudListPage/);
  });

  it("keeps /souls/new and /souls/:id/edit wired to SoulFormPage", () => {
    const source = readRoutes();

    expect(source).toMatch(/path:\s*["']souls\/new["']/);
    expect(source).toMatch(/path:\s*["']souls\/:id\/edit["']/);
    expect(source).toMatch(/SoulFormPage/);
  });
});
