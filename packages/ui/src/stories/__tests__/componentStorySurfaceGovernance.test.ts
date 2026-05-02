import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const TEST_DIR = dirname(fileURLToPath(import.meta.url));
const UI_SRC_DIR = resolve(TEST_DIR, "..", "..");
const COMPONENT_TEST_DIR = resolve(UI_SRC_DIR, "components", "ui", "__tests__");
const CENTRAL_OWNER_PATH = resolve(TEST_DIR, "componentStorySurface.test.ts");

const COMPONENT_CONTRACT_SUITE_EXCEPTIONS = [
  "composites.test.ts",
  "tagInput.test.ts",
] as const;

const EXPECTED_COMPONENT_CONTRACT_SUITES = [
  "buttonDialogContracts.test.ts",
  "composites.test.ts",
  "corePrimitiveContracts.test.ts",
  "feedbackPrimitiveContracts.test.ts",
  "formControlContracts.test.ts",
  "dataDisplayContracts.test.ts",
  "navigationContracts.test.ts",
  "overlayContracts.test.ts",
  "tagInput.test.ts",
] as const;

const STORYBOOK_OWNERSHIP_PATTERNS = [
  {
    label: "Storybook stories",
    pattern: /Storybook stories/,
  },
  {
    label: "readStory",
    pattern: /\breadStory\b/,
  },
  {
    label: "storyExists",
    pattern: /\bstoryExists\b/,
  },
  {
    label: "STORIES_DIR",
    pattern: /\bSTORIES_DIR\b/,
  },
  {
    label: "*.stories.tsx expectations",
    pattern: /\b[A-Z][A-Za-z0-9]*\.stories\.tsx\b/,
  },
] as const;

const EXPECTED_STORY_SURFACE = [
  "Button",
  "Badge",
  "Input",
  "Textarea",
  "Label",
  "Tooltip",
  "Spinner",
  "Skeleton",
  "Progress",
  "StatusDot",
  "Toast",
  "Select",
  "Switch",
  "Checkbox",
  "Radio",
  "Slider",
  "Table",
  "Card",
  "StatCard",
  "CodeBlock",
  "Dialog",
  "DropdownMenu",
  "Command",
  "Sheet",
  "Popover",
  "Tabs",
  "Breadcrumb",
  "Pagination",
] as const;

function readSource(filePath: string): string {
  return readFileSync(filePath, "utf-8");
}

function readCentralOwnerSource(): string {
  return existsSync(CENTRAL_OWNER_PATH) ? readSource(CENTRAL_OWNER_PATH) : "";
}

function discoverComponentContractSuites(): string[] {
  return readdirSync(COMPONENT_TEST_DIR)
    .filter((filename) => {
      return (
        filename.endsWith("Contracts.test.ts") ||
        COMPONENT_CONTRACT_SUITE_EXCEPTIONS.includes(
          filename as (typeof COMPONENT_CONTRACT_SUITE_EXCEPTIONS)[number],
        )
      );
    })
    .sort();
}

describe("component story surface governance boundary", () => {
  it("requires a central Storybook surface owner with governance metadata", () => {
    expect(
      existsSync(CENTRAL_OWNER_PATH),
      "packages/ui/src/stories/__tests__/componentStorySurface.test.ts must own component story existence and structure checks",
    ).toBe(true);

    const source = readCentralOwnerSource();

    for (const metadata of [
      "Governance:",
      "Owner:",
      "Boundary:",
      "Exit criteria:",
    ]) {
      expect(
        source.includes(metadata),
        `componentStorySurface.test.ts is missing ${metadata} metadata`,
      ).toBe(true);
    }
  });

  it("keeps Storybook ownership out of component contract suites", () => {
    const componentContractSuites = discoverComponentContractSuites();

    expect(componentContractSuites).toEqual(
      expect.arrayContaining([...EXPECTED_COMPONENT_CONTRACT_SUITES]),
    );

    const violations = componentContractSuites.flatMap((filename) => {
      const source = readSource(resolve(COMPONENT_TEST_DIR, filename));

      return STORYBOOK_OWNERSHIP_PATTERNS.flatMap(({ label, pattern }) => {
        return pattern.test(source) ? [`${filename}: ${label}`] : [];
      });
    });

    expect(
      violations,
      "component contract suites should not duplicate Storybook story ownership",
    ).toEqual([]);
  });

  it("requires the central owner source to name the representative component story surface", () => {
    const source = readCentralOwnerSource();
    const missingStories = EXPECTED_STORY_SURFACE.filter((storyName) => {
      return !source.includes(`${storyName}.stories.tsx`);
    });

    expect(
      missingStories,
      "componentStorySurface.test.ts should mention every representative tier story covered by the component surface contract",
    ).toEqual([]);
  });
});
