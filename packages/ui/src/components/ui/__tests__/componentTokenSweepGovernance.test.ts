import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const TEST_DIR = dirname(fileURLToPath(import.meta.url));
const SWEEP_TEST_PATH = resolve(TEST_DIR, "componentTokenSweep.test.ts");

function readSweepSource(): string {
  return readFileSync(SWEEP_TEST_PATH, "utf-8");
}

function countMatches(source: string, pattern: RegExp): number {
  return source.match(pattern)?.length ?? 0;
}

describe("component token sweep governance boundary", () => {
  it("documents why this source-text governance suite exists", () => {
    const source = readSweepSource();

    for (const metadata of [
      "Governance:",
      "Owner:",
      "Boundary:",
      "Exit criteria:",
    ]) {
      expect(
        source.includes(metadata),
        `missing ${metadata} metadata`,
      ).toBe(true);
    }
  });

  it("keeps the sweep compact enough to remain a boundary contract", () => {
    const source = readSweepSource();
    const lineCount = source.split(/\r?\n/).length;
    const describeCount = countMatches(source, /\bdescribe\(/g);

    expect(
      lineCount,
      "componentTokenSweep.test.ts should be table-driven, not a generated god-object test",
    ).toBeLessThanOrEqual(450);
    expect(
      describeCount,
      "describe blocks should name behaviors and boundaries, not every generated case",
    ).toBeLessThanOrEqual(8);
  });

  it("rejects generated per-component blocks for old token detectors", () => {
    const source = readSweepSource();
    const perComponentTailwindBlocks = countMatches(
      source,
      /describe\(\s*["'`]No old Tailwind tokens\s+[—-]\s+[^"'`]+\.tsx["'`]/g,
    );
    const perComponentVarBlocks = countMatches(
      source,
      /describe\(\s*["'`]No old var\(\) refs\s+[—-]\s+[^"'`]+\.tsx["'`]/g,
    );

    expect(perComponentTailwindBlocks).toBe(0);
    expect(perComponentVarBlocks).toBe(0);
  });

  it("rejects generated per-token completeness blocks", () => {
    const source = readSweepSource();

    expect(
      countMatches(
        source,
        /describe\(\s*["'`]Token sweep completeness:/g,
      ),
    ).toBe(0);
  });

  it("requires parameterized detector coverage instead of duplicated assertions", () => {
    const source = readSweepSource();

    expect(/\b(?:it|test)\.each\(/.test(source)).toBe(true);
    expect(/\bOLD_TOKEN_DETECTORS\b/.test(source)).toBe(true);
    expect(/\bCOMPONENT_TOKEN_CASES\b/.test(source)).toBe(true);
  });
});
