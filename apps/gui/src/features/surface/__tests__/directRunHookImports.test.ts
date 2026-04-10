import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const SURFACE_DIR = resolve(__dirname, "..");

function readSurfaceFile(relativePath: string): string {
  return readFileSync(resolve(SURFACE_DIR, relativePath), "utf-8");
}

describe("direct run hook imports", () => {
  it("WorkflowSurface imports and calls useRunRegressions directly", () => {
    const source = readSurfaceFile("WorkflowSurface.tsx");

    expect(source).toMatch(
      /import\s*\{[^}]*\buseRunRegressions\b[^}]*\}\s*from\s*["']@\/queries\/runs["']/,
    );
    expect(source).toMatch(/=\s*useRunRegressions\(/);
    expect(source).not.toMatch(/["']useRunRegressions["']\s+in\s+runQueries/);
    expect(source).not.toMatch(/\buseOptionalRunRegressions\b/);
  });

  it("useSurfaceHeaderSlots imports and calls useCancelRun directly", () => {
    const source = readSurfaceFile("useSurfaceHeaderSlots.tsx");

    expect(source).toMatch(
      /import\s*\{[^}]*\buseCancelRun\b[^}]*\}\s*from\s*["']@\/queries\/runs["']/,
    );
    expect(source).toMatch(/const\s+cancelRun\s*=\s*useCancelRun\(/);
    expect(source).not.toMatch(/["']useCancelRun["']\s+in\s+runQueries/);
    expect(source).not.toMatch(/\buseOptionalCancelRun\b/);
  });
});
