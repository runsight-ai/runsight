/**
 * Governance: screen token sweep test ownership boundary.
 *
 * Owner: GUI design-token migration governance.
 * Boundary: screenTokenSweep.test.ts may statically inspect GUI screen source
 * for retired design-token references, but it must read like a governance
 * contract instead of a broad feature behavior suite.
 * Exit criteria: remove this governance suite once the screen token sweep has
 * been renamed/reframed as design-token boundary governance and compressed
 * into one parameterized detector/helper contract that cannot regress into
 * generated per-token describe blocks.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const TARGET_TEST_PATH = resolve(__dirname, "screenTokenSweep.test.ts");
const MAX_GOVERNANCE_SWEEP_LINES = 450;
const MAX_GOVERNANCE_SWEEP_DESCRIBES = 12;

function readScreenTokenSweepTest(): string {
  return readFileSync(TARGET_TEST_PATH, "utf-8");
}

function countMatches(source: string, pattern: RegExp): number {
  return source.match(pattern)?.length ?? 0;
}

function hasGovernanceFrame(source: string): boolean {
  return [
    /\bGovernance:/,
    /\bOwner:/,
    /\bBoundary:/,
    /\bExit criteria:/,
  ].every((pattern) => pattern.test(source));
}

function hasParameterizedDetectorContract(source: string): boolean {
  return [
    /\b(?:describe|it|test)\.each\s*\(/,
    /\b[A-Z0-9_]*(?:DETECTORS|DETECTOR_CASES|TOKEN_SWEEP_CASES)\b[\s\S]*\b(?:flatMap|map)\s*\(/,
    /\b(?:run|collect|find)[A-Za-z]*(?:Sweep|Detector|Token)[A-Za-z]*\s*\([^)]*\)[\s\S]*\b(?:detectors|detectorCases|tokenSweepCases)\b/,
  ].some((pattern) => pattern.test(source));
}

function screenTokenSweepGovernanceGaps(source: string): string[] {
  const gaps: string[] = [];
  const lineCount = source.split(/\r?\n/).length;
  const describeCount = countMatches(source, /^\s*describe\(/gm);
  const generatedTokenDescribeCount = countMatches(
    source,
    /^\s*describe\(["']Token sweep completeness:/gm,
  );

  if (!hasGovernanceFrame(source)) {
    gaps.push("add Governance/Owner/Boundary/Exit criteria framing");
  }

  if (lineCount > MAX_GOVERNANCE_SWEEP_LINES) {
    gaps.push(
      `compress from ${lineCount} lines to <= ${MAX_GOVERNANCE_SWEEP_LINES}`,
    );
  }

  if (describeCount > MAX_GOVERNANCE_SWEEP_DESCRIBES) {
    gaps.push(
      `compress from ${describeCount} describe blocks to <= ${MAX_GOVERNANCE_SWEEP_DESCRIBES}`,
    );
  }

  if (generatedTokenDescribeCount > 0) {
    gaps.push(
      `replace ${generatedTokenDescribeCount} generated token-specific describe blocks with one detector contract`,
    );
  }

  if (!hasParameterizedDetectorContract(source)) {
    gaps.push(
      "use a parameterized detector/helper contract for token/file cases",
    );
  }

  return gaps;
}

describe("Governance: screen token sweep test ownership boundary", () => {
  it("keeps screen token migration coverage framed as compressed design-token governance", () => {
    const source = readScreenTokenSweepTest();
    const gaps = screenTokenSweepGovernanceGaps(source);

    expect(
      gaps,
      [
        "screenTokenSweep.test.ts should be a small governance/design-token boundary suite,",
        "with explicit owner/boundary/exit criteria and one parameterized detector/helper approach",
        "instead of broad feature-style groups or generated per-token describe blocks.",
      ].join(" "),
    ).toEqual([]);
  });
});
