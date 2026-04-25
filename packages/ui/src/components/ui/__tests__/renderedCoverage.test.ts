import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const PACKAGE_JSON_PATH = resolve(__dirname, "..", "..", "..", "..", "package.json");

const nonComponentExports = new Set(["./styles.css", "./runTable.styles", "./utils"]);

const renderedBaselineCoverage = {
  "./RunStatusDot": "renderedDisplayContracts.test.tsx",
  "./badge": "renderedDisplayContracts.test.tsx",
  "./button": "renderedFormControls.test.tsx",
  "./card": "renderedDisplayContracts.test.tsx",
  "./dialog": "renderedNavigationAndOverlays.test.tsx",
  "./dropdown-menu": "renderedNavigationAndOverlays.test.tsx",
  "./empty-state": "renderedDisplayContracts.test.tsx",
  "./input": "renderedFormControls.test.tsx",
  "./key-value": "renderedDisplayContracts.test.tsx",
  "./label": "renderedFormControls.test.tsx",
  "./select": "renderedNavigationAndOverlays.test.tsx",
  "./segmented-control": "renderedFormControls.test.tsx",
  "./skeleton": "renderedDisplayContracts.test.tsx",
  "./slider": "renderedFormControls.test.tsx",
  "./stat-card": "renderedDisplayContracts.test.tsx",
  "./status-dot": "renderedDisplayContracts.test.tsx",
  "./switch": "renderedFormControls.test.tsx",
  "./table": "renderedNavigationAndOverlays.test.tsx",
  "./tag-input": "renderedFormControls.test.tsx",
  "./tabs": "renderedNavigationAndOverlays.test.tsx",
  "./textarea": "renderedFormControls.test.tsx",
  "./tooltip": "renderedNavigationAndOverlays.test.tsx",
} as const;

function readRetainedComponentExports() {
  const packageJson = JSON.parse(readFileSync(PACKAGE_JSON_PATH, "utf8")) as {
    exports?: Record<string, unknown>;
  };

  return Object.keys(packageJson.exports ?? {})
    .filter((subpath) => !nonComponentExports.has(subpath))
    .sort();
}

describe("RUN-977 rendered component coverage structure", () => {
  it("assigns every retained component export to a rendered baseline suite", () => {
    expect(Object.keys(renderedBaselineCoverage).sort()).toEqual(readRetainedComponentExports());
  });

  it("keeps rendered component coverage grouped by the canonical baseline suites", () => {
    const canonicalSuites = new Set([
      "renderedDisplayContracts.test.tsx",
      "renderedFormControls.test.tsx",
      "renderedNavigationAndOverlays.test.tsx",
    ]);

    const nonCanonicalAssignments = Object.entries(renderedBaselineCoverage)
      .filter(([, suite]) => !canonicalSuites.has(suite))
      .map(([subpath, suite]) => `${subpath} -> ${suite}`);

    expect(nonCanonicalAssignments).toEqual([]);
  });
});

