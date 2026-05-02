import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * Governance: packages/ui primitive contract tests must be stable owner suites,
 * not chronology or implementation-phase suites.
 * Owner: packages/ui design-system primitive contract coverage.
 * Boundary: source-text governance for test ownership, naming, metadata, and
 * compact table-driven structure under src/components/ui/__tests__ only.
 * Exit criteria: keep compact owner suites that expose explicit contract data tables.
 */

const TEST_DIR = dirname(fileURLToPath(import.meta.url));

const REQUIRED_METADATA = [
  "Governance:",
  "Owner:",
  "Boundary:",
  "Exit criteria:",
] as const;

const OWNER_SUITES = [
  {
    filename: "corePrimitiveContracts.test.ts",
    contractDataName: "CORE_PRIMITIVE_CONTRACTS",
    components: ["Button", "Badge", "Input", "Textarea", "Label", "Tooltip"],
  },
  {
    filename: "feedbackPrimitiveContracts.test.ts",
    contractDataName: "FEEDBACK_PRIMITIVE_CONTRACTS",
    components: ["Spinner", "Skeleton", "Progress", "StatusDot", "Toast"],
  },
] as const;

const APPROVED_PRIMITIVE_TEST_FILES = new Set([
  "corePrimitiveContracts.test.ts",
  "feedbackPrimitiveContracts.test.ts",
  "primitiveContractGovernance.test.ts",
]);

function testPath(filename: string): string {
  return resolve(TEST_DIR, filename);
}

function readTestSource(filename: string): string {
  const path = testPath(filename);
  return existsSync(path) ? readFileSync(path, "utf-8") : "";
}

function countMatches(source: string, pattern: RegExp): number {
  return source.match(pattern)?.length ?? 0;
}

describe("primitive contract governance boundary", () => {
  it("rejects unapproved primitive contract test filenames", () => {
    const unapprovedPrimitiveSuites = readdirSync(TEST_DIR).filter((filename) =>
      /Primitive.*\.test\.tsx?$/i.test(filename) &&
        !APPROVED_PRIMITIVE_TEST_FILES.has(filename),
    );

    expect(
      unapprovedPrimitiveSuites,
      "primitive contract tests should use behavior, feature, or boundary owner names",
    ).toEqual([]);
  });

  it("requires stable owner suites for core and feedback primitive contracts", () => {
    for (const suite of OWNER_SUITES) {
      expect(
        existsSync(testPath(suite.filename)),
        `${suite.filename} must own ${suite.components.join(", ")} contract coverage`,
      ).toBe(true);
    }
  });

  it("requires each stable owner suite to document governance ownership and exit criteria", () => {
    for (const suite of OWNER_SUITES) {
      const source = readTestSource(suite.filename);

      for (const metadata of REQUIRED_METADATA) {
        expect(
          source.includes(metadata),
          `${suite.filename} is missing ${metadata} metadata`,
        ).toBe(true);
      }
    }
  });

  it("keeps stable owner suites compact enough to avoid generated describe blocks", () => {
    for (const suite of OWNER_SUITES) {
      const source = readTestSource(suite.filename);
      const lineCount = source.split(/\r?\n/).length;
      const describeCount = countMatches(source, /\bdescribe\s*\(/g);

      expect(
        lineCount,
        `${suite.filename} should stay table-driven instead of becoming a god-object suite`,
      ).toBeLessThanOrEqual(420);
      expect(
        describeCount,
        `${suite.filename} should name owner-level behaviors and boundaries, not every generated concern`,
      ).toBeLessThanOrEqual(10);
    }
  });

  it("requires table-driven primitive contract data owned by each stable suite", () => {
    for (const suite of OWNER_SUITES) {
      const source = readTestSource(suite.filename);

      expect(
        new RegExp(`\\b${suite.contractDataName}\\b`).test(source),
        `${suite.filename} must expose ${suite.contractDataName} as explicit contract data`,
      ).toBe(true);
      expect(
        /\b(?:it|test)\.each\(/.test(source),
        `${suite.filename} should execute contract rows through table-driven coverage`,
      ).toBe(true);

      for (const component of suite.components) {
        expect(
          new RegExp(`\\b${component}\\b`).test(source),
          `${suite.filename} must explicitly own ${component} contract coverage`,
        ).toBe(true);
      }
    }
  });
});
