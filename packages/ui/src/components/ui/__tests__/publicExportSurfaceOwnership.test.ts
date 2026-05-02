import { readFileSync, readdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * Governance: packages/ui component and public-export tests own package
 * surface coverage only.
 * Owner: packages/ui component public export coverage.
 * Boundary: source-text governance for component/public-export tests under
 * src/components/ui/__tests__; app runtime import scanning belongs to apps/gui,
 * and Storybook surface coverage belongs to src/stories/__tests__.
 * Exit criteria: remove this only after package export governance no longer
 * risks reabsorbing app import or Storybook ownership.
 */

const TEST_DIR = dirname(fileURLToPath(import.meta.url));
const THIS_FILE = "publicExportSurfaceOwnership.test.ts";

const GUI_IMPORT_OWNERSHIP_PATTERNS = [
  {
    label: "GUI source directory constant",
    pattern: /\bGUI_SRC_DIR\b/,
  },
  {
    label: "GUI import collection helper",
    pattern: /\bgetGuiUiImportSubpaths\b/,
  },
  {
    label: "apps/gui source traversal",
    pattern: /apps["']?,\s*["']gui["']?|apps\/gui/,
  },
] as const;

const STORYBOOK_COVERAGE_OWNERSHIP_PATTERNS = [
  {
    label: "Storybook directory constant",
    pattern: /\bSTORIES_DIR\b/,
  },
  {
    label: "story coverage helper",
    pattern: /\bhasStoryCoverage\b/,
  },
  {
    label: "story files as coverage proof",
    pattern: /\.stories\.tsx\b/,
  },
] as const;

function componentUiTestFiles(): string[] {
  return readdirSync(TEST_DIR)
    .filter((filename) => /\.test\.tsx?$/.test(filename))
    .filter((filename) => filename !== THIS_FILE)
    .sort();
}

function findPatternViolations(
  patterns: typeof GUI_IMPORT_OWNERSHIP_PATTERNS,
): string[] {
  return componentUiTestFiles().flatMap((filename) => {
    const source = readFileSync(resolve(TEST_DIR, filename), "utf-8");

    return patterns.flatMap(({ label, pattern }) => {
      return pattern.test(source) ? [`${filename}: ${label}`] : [];
    });
  });
}

describe("package ui public export ownership boundary", () => {
  it("keeps GUI runtime import scanning in the app-owned supported surface suite", () => {
    const violations = findPatternViolations(GUI_IMPORT_OWNERSHIP_PATTERNS);

    expect(
      violations,
      "packages/ui component/public-export tests should not scan apps/gui; apps/gui/src/utils/__tests__/uiSupportedSurface.test.ts owns that import contract",
    ).toEqual([]);
  });

  it("keeps Storybook story presence out of package export proof", () => {
    const violations = findPatternViolations(
      STORYBOOK_COVERAGE_OWNERSHIP_PATTERNS,
    );

    expect(
      violations,
      "packages/ui component/public-export tests should use package component/test ownership, while packages/ui/src/stories/__tests__/componentStorySurface.test.ts owns Storybook presence",
    ).toEqual([]);
  });
});
