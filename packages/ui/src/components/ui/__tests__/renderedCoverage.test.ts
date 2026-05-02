import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import {
  canonicalSuites,
  componentModules,
  nonComponentNamedExports,
  renderedBaselineCoverage,
  renderedComponentEvidence,
  type CanonicalSuite,
  type CoveredSubpath,
} from "./fixtures/renderedCoverageManifest";

const PACKAGE_JSON_PATH = resolve(__dirname, "..", "..", "..", "..", "package.json");

const nonComponentExports = new Set(["./styles.css", "./runTable.styles", "./utils"]);

const canonicalSuitePaths: Record<CanonicalSuite, string> = {
  "renderedDisplayContracts.test.tsx": resolve(__dirname, "renderedDisplayContracts.test.tsx"),
  "renderedFormControls.test.tsx": resolve(__dirname, "renderedFormControls.test.tsx"),
  "renderedNavigationAndOverlays.test.tsx": resolve(__dirname, "renderedNavigationAndOverlays.test.tsx"),
};

function readRetainedComponentExports() {
  const packageJson = JSON.parse(readFileSync(PACKAGE_JSON_PATH, "utf8")) as {
    exports?: Record<string, unknown>;
  };

  return Object.keys(packageJson.exports ?? {})
    .filter((subpath) => !nonComponentExports.has(subpath))
    .sort();
}

function readRuntimeComponentNames(subpath: CoveredSubpath) {
  const ignoredExports = new Set(nonComponentNamedExports[subpath] ?? []);

  return Object.keys(componentModules[subpath])
    .filter((exportName) => !ignoredExports.has(exportName))
    .sort();
}

const suiteSourceCache = new Map<CanonicalSuite, string>();

function readSuiteSource(suite: CanonicalSuite) {
  const cachedSource = suiteSourceCache.get(suite);

  if (cachedSource) {
    return cachedSource;
  }

  const source = readFileSync(canonicalSuitePaths[suite], "utf8");
  suiteSourceCache.set(suite, source);
  return source;
}

function hasRenderedJsxTag(source: string, componentName: string) {
  return new RegExp(`<${componentName}(?:[\\s>/])`).test(source);
}

describe("rendered component coverage structure", () => {
  it("assigns every retained component export to a rendered baseline suite", () => {
    expect(Object.keys(renderedBaselineCoverage).sort()).toEqual(readRetainedComponentExports());
  });

  it("lists every public named component export inside its baseline assignment", () => {
    const uncoveredComponents = Object.entries(renderedBaselineCoverage).flatMap(
      ([subpath, assignment]) => {
        const coveredComponents = new Set(assignment.components);

        return readRuntimeComponentNames(subpath as CoveredSubpath)
          .filter((componentName) => !coveredComponents.has(componentName))
          .map((componentName) => `${subpath} -> ${componentName}`);
      },
    );
    const staleComponents = Object.entries(renderedBaselineCoverage).flatMap(
      ([subpath, assignment]) => {
        const runtimeComponents = new Set(readRuntimeComponentNames(subpath as CoveredSubpath));

        return assignment.components
          .filter((componentName) => !runtimeComponents.has(componentName))
          .map((componentName) => `${subpath} -> ${componentName}`);
      },
    );

    expect(uncoveredComponents).toEqual([]);
    expect(staleComponents).toEqual([]);
  });

  it("requires explicit rendered assertion evidence for every public component export", () => {
    const missingEvidence = Object.entries(renderedBaselineCoverage).flatMap(
      ([subpath, assignment]) => {
        const evidence = renderedComponentEvidence[subpath as CoveredSubpath];

        return assignment.components
          .filter((componentName) => !evidence[componentName])
          .map((componentName) => `${subpath} -> ${componentName}`);
      },
    );
    const staleEvidence = Object.entries(renderedComponentEvidence).flatMap(
      ([subpath, evidence]) => {
        const coveredComponents = new Set(renderedBaselineCoverage[subpath as CoveredSubpath].components);

        return Object.keys(evidence)
          .filter((componentName) => !coveredComponents.has(componentName))
          .map((componentName) => `${subpath} -> ${componentName}`);
      },
    );
    const missingRenderedTags = Object.entries(renderedBaselineCoverage).flatMap(
      ([subpath, assignment]) => {
        const source = readSuiteSource(assignment.suite);

        return assignment.components
          .filter((componentName) => !hasRenderedJsxTag(source, componentName))
          .map((componentName) => `${subpath} -> ${componentName}`);
      },
    );
    const missingTestNames = Object.entries(renderedBaselineCoverage).flatMap(
      ([subpath, assignment]) => {
        const source = readSuiteSource(assignment.suite);
        const evidence = renderedComponentEvidence[subpath as CoveredSubpath];

        return assignment.components
          .filter((componentName) => {
            const componentEvidence = evidence[componentName];
            return componentEvidence && !source.includes(`it("${componentEvidence.testName}"`);
          })
          .map((componentName) => `${subpath} -> ${componentName}`);
      },
    );
    const missingAssertionTokens = Object.entries(renderedBaselineCoverage).flatMap(
      ([subpath, assignment]) => {
        const source = readSuiteSource(assignment.suite);
        const evidence = renderedComponentEvidence[subpath as CoveredSubpath];

        return assignment.components
          .filter((componentName) => {
            const componentEvidence = evidence[componentName];
            return componentEvidence && !source.includes(componentEvidence.assertionToken);
          })
          .map((componentName) => `${subpath} -> ${componentName}`);
      },
    );

    expect(missingEvidence).toEqual([]);
    expect(staleEvidence).toEqual([]);
    expect(missingRenderedTags).toEqual([]);
    expect(missingTestNames).toEqual([]);
    expect(missingAssertionTokens).toEqual([]);
  });

  it("keeps rendered component coverage grouped by the canonical baseline suites", () => {
    const canonicalSuiteSet = new Set(canonicalSuites);

    const nonCanonicalAssignments = Object.entries(renderedBaselineCoverage)
      .filter(([, assignment]) => !canonicalSuiteSet.has(assignment.suite))
      .map(([subpath, assignment]) => `${subpath} -> ${assignment.suite}`);

    expect(nonCanonicalAssignments).toEqual([]);
  });
});
