import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/*
 * Governance: This suite owns representative component story existence and
 * minimum CSF structure coverage.
 * Owner: packages/ui Storybook component surface.
 * Boundary: representative packages/ui/src/stories/*.stories.tsx files only;
 * component contract suites should not duplicate Storybook content checks.
 * Exit criteria: remove or split this suite only after another behavior-named
 * owner verifies representative story existence and CSF structure.
 */

const TEST_DIR = dirname(fileURLToPath(import.meta.url));
const STORIES_DIR = resolve(TEST_DIR, "..");

const REPRESENTATIVE_COMPONENT_STORIES = [
  "Button.stories.tsx",
  "Input.stories.tsx",
  "Select.stories.tsx",
  "Table.stories.tsx",
  "Dialog.stories.tsx",
  "Tabs.stories.tsx",
  "Tooltip.stories.tsx",
] as const;

const REPRESENTATIVE_STORY_SCENARIOS = [
  {
    filename: "Button.stories.tsx",
    expectations: [/primary/i, /loading/i, /icon.?only/i],
  },
  {
    filename: "Select.stories.tsx",
    expectations: [/Default/i, /Disabled/i],
  },
  {
    filename: "Dialog.stories.tsx",
    expectations: [/DialogFooter/, /Button/],
  },
  {
    filename: "Tabs.stories.tsx",
    expectations: [/Default/i, /TabsTrigger/],
  },
] as const;

function storyPath(filename: string): string {
  return resolve(STORIES_DIR, filename);
}

function readStory(filename: string): string {
  return readFileSync(storyPath(filename), "utf-8");
}

describe("component story surface smoke", () => {
  it("keeps representative component story files in the package story surface", () => {
    const missingStories = REPRESENTATIVE_COMPONENT_STORIES.filter(
      (filename) => !existsSync(storyPath(filename)),
    );

    expect(missingStories).toEqual([]);
  });

  it.each(REPRESENTATIVE_COMPONENT_STORIES)(
    "%s has minimum Storybook CSF structure",
    (filename) => {
      const source = readStory(filename);

      expect(source).toMatch(/export\s+default\s+/);
      expect(source).toMatch(/\btitle\s*:/);
      expect(source).toMatch(/export\s+const\s+\w+/);
    },
  );

  it.each(REPRESENTATIVE_STORY_SCENARIOS)(
    "$filename preserves representative scenario coverage",
    ({ filename, expectations }) => {
      const source = readStory(filename);

      for (const pattern of expectations) {
        expect(source).toMatch(pattern);
      }
    },
  );
});
