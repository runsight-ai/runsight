/**
 * RED-TEAM tests for RUN-863: Prune 17 unused UI components.
 *
 * Validates that all 17 unused components and their corresponding
 * story files have been deleted from the packages/ui package, and
 * that package.json exports contain no references to these components.
 *
 * Expected failures (current state — before Green phase):
 *   - All 17 component .tsx files still exist on disk
 *   - All 17 story .tsx files still exist on disk
 *   - package.json exports currently do NOT include them (already clean)
 */

import { describe, it, expect } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

// __dirname = packages/ui/src/components/ui/__tests__
const UI_DIR = path.resolve(__dirname, "../");
const STORIES_DIR = path.resolve(__dirname, "../../../stories");
const PKG_JSON = path.resolve(__dirname, "../../../../package.json");

const PRUNED_COMPONENTS = [
  "avatar",
  "breadcrumb",
  "checkbox",
  "code-block",
  "command",
  "divider",
  "field",
  "icon",
  "link",
  "node-card",
  "pagination",
  "popover",
  "progress",
  "radio",
  "sheet",
  "spinner",
  "toast",
] as const;

/** Map component slug → expected story filename (PascalCase). */
const STORY_FILE_MAP: Record<string, string> = {
  avatar: "Avatar.stories.tsx",
  breadcrumb: "Breadcrumb.stories.tsx",
  checkbox: "Checkbox.stories.tsx",
  "code-block": "CodeBlock.stories.tsx",
  command: "Command.stories.tsx",
  divider: "Divider.stories.tsx",
  field: "Field.stories.tsx",
  icon: "Icon.stories.tsx",
  link: "Link.stories.tsx",
  "node-card": "NodeCard.stories.tsx",
  pagination: "Pagination.stories.tsx",
  popover: "Popover.stories.tsx",
  progress: "Progress.stories.tsx",
  radio: "Radio.stories.tsx",
  sheet: "Sheet.stories.tsx",
  spinner: "Spinner.stories.tsx",
  toast: "Toast.stories.tsx",
};

describe("RUN-863: pruned component files do not exist", () => {
  for (const name of PRUNED_COMPONENTS) {
    it(`${name}.tsx must not exist`, () => {
      const filePath = path.join(UI_DIR, `${name}.tsx`);
      expect(
        existsSync(filePath),
        `Expected ${name}.tsx to be deleted but it still exists at ${filePath}`,
      ).toBe(false);
    });
  }
});

describe("RUN-863: pruned story files do not exist", () => {
  for (const name of PRUNED_COMPONENTS) {
    const storyFile = STORY_FILE_MAP[name];
    it(`${storyFile} must not exist`, () => {
      const filePath = path.join(STORIES_DIR, storyFile);
      expect(
        existsSync(filePath),
        `Expected ${storyFile} to be deleted but it still exists at ${filePath}`,
      ).toBe(false);
    });
  }
});

describe("RUN-863: package.json exports contain no pruned component entries", () => {
  it("package.json exports object has no keys matching pruned component paths", () => {
    const pkg = JSON.parse(readFileSync(PKG_JSON, "utf-8")) as {
      exports?: Record<string, string>;
    };
    const exports = pkg.exports ?? {};

    const pruned_export_keys = Object.keys(exports).filter((key) => {
      // Match export keys like "./avatar" or "./code-block"
      // and export values referencing pruned component paths
      const slug = key.replace(/^\.\//, "");
      return PRUNED_COMPONENTS.includes(slug as (typeof PRUNED_COMPONENTS)[number]);
    });

    expect(
      pruned_export_keys,
      `package.json still exports pruned components: ${pruned_export_keys.join(", ")}`,
    ).toHaveLength(0);

    // Also assert no export value points to a pruned component file
    const pruned_export_values = Object.entries(exports).filter(([, value]) =>
      PRUNED_COMPONENTS.some((name) => value.includes(`/ui/${name}.tsx`)),
    );

    expect(
      pruned_export_values,
      `package.json export values still reference pruned files: ${pruned_export_values.map(([k]) => k).join(", ")}`,
    ).toHaveLength(0);
  });
});
