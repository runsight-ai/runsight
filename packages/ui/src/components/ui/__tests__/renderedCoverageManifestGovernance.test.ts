import { existsSync, readFileSync } from "node:fs";
import { dirname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * Governance: rendered component coverage must keep fixture data out of the
 * validator suite.
 * Owner: packages/ui rendered component coverage validator.
 * Boundary: source-text governance for the rendered coverage validator and its
 * package-local fixture under src/components/ui/__tests__ only.
 * Exit criteria: move manifest and evidence data into fixtures/renderedCoverageManifest.ts.
 */

const TEST_DIR = dirname(fileURLToPath(import.meta.url));
const RENDERED_COVERAGE_TEST_PATH = resolve(TEST_DIR, "renderedCoverage.test.ts");
const RENDERED_COVERAGE_FIXTURE_PATH = resolve(
  TEST_DIR,
  "fixtures",
  "renderedCoverageManifest.ts",
);

const INLINE_MANIFEST_EXPORTS = [
  "renderedBaselineCoverage",
  "componentModules",
  "nonComponentNamedExports",
  "renderedComponentEvidence",
] as const;

function readRenderedCoverageSource(): string {
  return readFileSync(RENDERED_COVERAGE_TEST_PATH, "utf-8");
}

function hasInlineDefinition(source: string, name: string): boolean {
  return new RegExp(`^\\s*const\\s+${name}(?:\\s*:[^=]+)?\\s*=`, "m").test(source);
}

describe("rendered coverage manifest governance boundary", () => {
  it("requires manifest data to live in the package-local fixture while the validator keeps ownership", () => {
    const source = readRenderedCoverageSource();
    const fixtureRelativePath = relative(TEST_DIR, RENDERED_COVERAGE_FIXTURE_PATH);
    const violations: string[] = [];

    if (!existsSync(RENDERED_COVERAGE_FIXTURE_PATH)) {
      violations.push(`missing package-local fixture: ${fixtureRelativePath}`);
    }

    if (!source.includes("./fixtures/renderedCoverageManifest")) {
      violations.push("renderedCoverage.test.ts must import manifest data from ./fixtures/renderedCoverageManifest");
    }

    for (const name of INLINE_MANIFEST_EXPORTS) {
      if (hasInlineDefinition(source, name)) {
        violations.push(`${name} is still defined inline in renderedCoverage.test.ts`);
      }
    }

    if (!source.includes('describe("rendered component coverage structure"')) {
      violations.push("renderedCoverage.test.ts must remain the rendered component coverage validator suite");
    }

    expect(violations).toEqual([]);
  });
});
