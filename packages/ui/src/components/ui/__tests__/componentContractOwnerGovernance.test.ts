import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * Governance: packages/ui component contract tests must stay as stable owner
 * smoke suites rather than expanding into duplicate rendered behavior coverage.
 * Owner: packages/ui design-system component contract coverage.
 * Boundary: manifest checks for source-contract owner suites under
 * src/components/ui/__tests__ only.
 * Exit criteria: remove this once package UI test ownership is enforced by a
 * dedicated test registry or lint rule.
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
  {
    filename: "formControlContracts.test.ts",
    contractDataName: "FORM_CONTROL_CONTRACTS",
    components: ["Select", "Switch", "Checkbox", "Radio", "Slider", "TagInput"],
  },
  {
    filename: "dataDisplayContracts.test.ts",
    contractDataName: "DATA_DISPLAY_CONTRACTS",
    components: ["Table", "Card", "StatCard", "CodeBlock"],
  },
  {
    filename: "navigationContracts.test.ts",
    contractDataName: "NAVIGATION_CONTRACTS",
    components: ["Tabs", "Breadcrumb", "Pagination"],
  },
  {
    filename: "overlayContracts.test.ts",
    contractDataName: "OVERLAY_CONTRACTS",
    components: ["Dialog", "DropdownMenu", "Command", "Sheet", "Popover"],
  },
] as const;

const RENDERED_OWNER_SUITES = [
  "renderedDisplayContracts.test.tsx",
  "renderedFormControls.test.tsx",
  "renderedOverlayPrimitives.test.tsx",
  "renderedTabsAndTables.test.tsx",
] as const;

function testPath(filename: string): string {
  return resolve(TEST_DIR, filename);
}

function readTestSource(filename: string): string {
  return readFileSync(testPath(filename), "utf-8");
}

describe("component contract owner governance smoke", () => {
  it.each(OWNER_SUITES)(
    "$filename keeps a stable source-contract owner manifest",
    ({ filename, contractDataName, components }) => {
      expect(existsSync(testPath(filename))).toBe(true);

      const source = readTestSource(filename);

      for (const metadata of REQUIRED_METADATA) {
        expect(source).toContain(metadata);
      }
      expect(source).toContain(`export const ${contractDataName}`);
      for (const component of components) {
        expect(source).toContain(component);
      }
    },
  );

  it("keeps rendered behavior in rendered owner suites", () => {
    for (const filename of RENDERED_OWNER_SUITES) {
      expect(existsSync(testPath(filename))).toBe(true);
    }
  });
});
