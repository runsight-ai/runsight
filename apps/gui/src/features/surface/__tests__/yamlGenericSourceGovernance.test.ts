import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

function readSurfaceSource(relativePath: string): string {
  const canvasDir = resolve(__dirname, "..");
  return readFileSync(resolve(canvasDir, relativePath), "utf-8");
}

describe("generic YAML compiler source governance", () => {
  const source = readSurfaceSource("yamlCompiler.ts");

  it("does not reintroduce hardcoded compiler field maps or known-type branching", () => {
    expect(source).not.toMatch(/\bBLOCK_TYPE_FIELDS\b/);
    expect(source).not.toMatch(/\bCAMEL_TO_SNAKE\b/);
    expect(source).not.toMatch(/\bSNAKE_TO_CAMEL\b/);
    expect(source).not.toMatch(/\bUNIVERSAL_FIELDS\b/);
    expect(source).not.toMatch(/\bNESTED_OBJECT_FIELDS\b/);
    expect(source).not.toMatch(/\bisKnownType\b/);
  });
});

describe("generic YAML parser source governance", () => {
  const source = readSurfaceSource("yamlParser.ts");

  it("does not reintroduce parser known-type allowlists or fallback guards", () => {
    expect(source).not.toMatch(/\bKNOWN_BLOCK_TYPES\b/);
    expect(source).not.toMatch(/\bVALID_STEP_TYPES\b/);
    expect(source).not.toMatch(/\bhandledSnakeFields\b/);
  });
});
