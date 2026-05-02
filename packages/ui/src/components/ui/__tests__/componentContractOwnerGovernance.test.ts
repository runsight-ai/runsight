import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * Governance: packages/ui component contract tests must be stable owner suites.
 * Owner: packages/ui design-system component contract coverage.
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
    filename: "formControlContracts.test.ts",
    contractDataName: "FORM_CONTROL_CONTRACTS",
    components: ["Select", "Switch", "Checkbox", "Radio", "Slider"],
    activeNameKeywords: ["formcontrols", "formcontrolcontracts"],
  },
  {
    filename: "dataDisplayContracts.test.ts",
    contractDataName: "DATA_DISPLAY_CONTRACTS",
    components: ["Table", "Card", "StatCard", "CodeBlock"],
    activeNameKeywords: ["datadisplay", "datadisplaycontracts"],
  },
  {
    filename: "navigationContracts.test.ts",
    contractDataName: "NAVIGATION_CONTRACTS",
    components: ["Tabs", "Breadcrumb", "Pagination"],
    activeNameKeywords: ["navigation", "navigationcontracts"],
  },
  {
    filename: "overlayContracts.test.ts",
    contractDataName: "OVERLAY_CONTRACTS",
    components: ["Dialog", "DropdownMenu", "Command", "Sheet", "Popover"],
    activeNameKeywords: ["overlays", "overlaycontracts"],
  },
] as const;

const TAG_INPUT_STATIC_CONTRACT_FILE = "tagInput.test.ts";
const RENDERED_FORM_CONTROLS_FILE = "renderedFormControls.test.tsx";
const TAG_INPUT_RENDERED_BEHAVIOR_TEST_NAME =
  "adds, deduplicates, and removes tags through the rendered tag-input surface";

const TAG_INPUT_SOURCE_BEHAVIOR_MARKERS = [
  {
    name: "TagInput behavior contracts suite",
    pattern: /\bdescribe\s*\(\s*["'`]TagInput behavior contracts["'`]/,
  },
  {
    name: "keyboard event source assertions",
    pattern: /e\\?\.key|Backspace/,
  },
  {
    name: "source implementation helper assertions",
    pattern: /\b(?:addTag|removeTag)\b/,
  },
  {
    name: "placeholder behavior source assertions",
    pattern: /placeholder\s*=|tag count|tags\.length/,
  },
] as const;

const APPROVED_COMPONENT_CONTRACT_TEST_FILES = new Set([
  "componentContractOwnerGovernance.test.ts",
  ...OWNER_SUITES.map((suite) => suite.filename),
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

function ownsComponentContractGroup(filename: string): boolean {
  const normalizedFilename = filename.toLowerCase();

  if (normalizedFilename.startsWith("rendered")) {
    return false;
  }

  return OWNER_SUITES.some((suite) =>
    suite.activeNameKeywords.some((keyword) =>
      normalizedFilename.includes(keyword),
    ),
  );
}

describe("component contract owner governance boundary", () => {
  it("rejects unapproved component contract group filenames", () => {
    const unapprovedComponentContractSuites = readdirSync(TEST_DIR).filter(
      (filename) =>
        /\.test\.tsx?$/.test(filename) &&
        ownsComponentContractGroup(filename) &&
        !APPROVED_COMPONENT_CONTRACT_TEST_FILES.has(filename),
    );

    expect(
      unapprovedComponentContractSuites,
      "component contract tests should use behavior, feature, or boundary owner names",
    ).toEqual([]);
  });

  it("requires stable owner suites for component contract groups", () => {
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

  it("keeps stable owner suites compact enough for table-driven ownership", () => {
    for (const suite of OWNER_SUITES) {
      const source = readTestSource(suite.filename);
      const lineCount = source.split(/\r?\n/).length;
      const describeCount = countMatches(source, /\bdescribe\s*\(/g);

      expect(
        lineCount,
        `${suite.filename} should stay compact instead of becoming a god-object suite`,
      ).toBeLessThanOrEqual(320);
      expect(
        describeCount,
        `${suite.filename} should name owner-level behaviors and boundaries`,
      ).toBeLessThanOrEqual(8);
    }
  });

  it("requires table-driven component contract data owned by each stable suite", () => {
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

  it("keeps rendered TagInput behavior owned by the rendered form-control suite", () => {
    const tagInputSource = readTestSource(TAG_INPUT_STATIC_CONTRACT_FILE);
    const renderedFormControlSource = readTestSource(
      RENDERED_FORM_CONTROLS_FILE,
    );
    const mirroredBehaviorMarkers = TAG_INPUT_SOURCE_BEHAVIOR_MARKERS.filter(
      (marker) => marker.pattern.test(tagInputSource),
    ).map((marker) => marker.name);

    expect(
      renderedFormControlSource,
      `${RENDERED_FORM_CONTROLS_FILE} must remain the rendered TagInput behavior owner`,
    ).toContain("TagInput");
    expect(
      renderedFormControlSource,
      `${RENDERED_FORM_CONTROLS_FILE} must cover the rendered TagInput add, dedupe, remove, keyboard, and placeholder behavior`,
    ).toContain(TAG_INPUT_RENDERED_BEHAVIOR_TEST_NAME);
    expect(
      mirroredBehaviorMarkers,
      `${TAG_INPUT_STATIC_CONTRACT_FILE} may own file/export/API/static visual contracts, but rendered user behavior belongs in ${RENDERED_FORM_CONTROLS_FILE}`,
    ).toEqual([]);
  });
});
