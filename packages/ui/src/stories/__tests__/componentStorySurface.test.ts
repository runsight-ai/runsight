import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/*
 * Governance: This suite is the central owner for representative component
 * story existence and minimum CSF structure coverage.
 * Owner: packages/ui Storybook component surface.
 * Boundary: packages/ui/src/stories/*.stories.tsx only; component contract
 * suites should not duplicate these checks.
 * Exit criteria: remove or split this suite only after another behavior-named
 * owner verifies the same story existence and default export/title/named story
 * structure for the representative surface.
 */

const TEST_DIR = dirname(fileURLToPath(import.meta.url));
const STORIES_DIR = resolve(TEST_DIR, "..");

const COMPONENT_STORY_SURFACE = [
  "Button.stories.tsx",
  "Badge.stories.tsx",
  "Input.stories.tsx",
  "Textarea.stories.tsx",
  "Label.stories.tsx",
  "Tooltip.stories.tsx",
  "Spinner.stories.tsx",
  "Skeleton.stories.tsx",
  "Progress.stories.tsx",
  "StatusDot.stories.tsx",
  "Toast.stories.tsx",
  "Select.stories.tsx",
  "Switch.stories.tsx",
  "Checkbox.stories.tsx",
  "Radio.stories.tsx",
  "Slider.stories.tsx",
  "Table.stories.tsx",
  "Card.stories.tsx",
  "StatCard.stories.tsx",
  "CodeBlock.stories.tsx",
  "Dialog.stories.tsx",
  "DropdownMenu.stories.tsx",
  "Command.stories.tsx",
  "Sheet.stories.tsx",
  "Popover.stories.tsx",
  "Tabs.stories.tsx",
  "Breadcrumb.stories.tsx",
  "Pagination.stories.tsx",
] as const;

type StoryContentExpectation = {
  label: string;
  pattern: RegExp;
};

type ComponentStoryScenario = {
  filename: (typeof COMPONENT_STORY_SURFACE)[number];
  expectations: StoryContentExpectation[];
};

const BASIC_USAGE_PATTERN = /Default|Basic|Primary/i;

const COMPONENT_STORY_SCENARIOS: ComponentStoryScenario[] = [
  {
    filename: "Button.stories.tsx",
    expectations: [
      { label: "primary variant", pattern: /primary/i },
      { label: "loading state", pattern: /loading/i },
      { label: "icon-only variant", pattern: /icon.?only/i },
    ],
  },
  {
    filename: "Badge.stories.tsx",
    expectations: [
      {
        label: "semantic variants",
        pattern: /success|warning|danger|info/i,
      },
      { label: "dot indicator", pattern: /dot/i },
    ],
  },
  {
    filename: "Spinner.stories.tsx",
    expectations: [
      { label: "sm size", pattern: /\bsm\b/i },
      { label: "accent variant", pattern: /accent/i },
    ],
  },
  {
    filename: "Skeleton.stories.tsx",
    expectations: [
      { label: "text variant", pattern: /\btext\b/i },
      { label: "avatar variant", pattern: /avatar/i },
    ],
  },
  {
    filename: "Progress.stories.tsx",
    expectations: [
      { label: "indeterminate state", pattern: /indeterminate/i },
      { label: "success or danger variant", pattern: /success|danger/i },
    ],
  },
  {
    filename: "StatusDot.stories.tsx",
    expectations: [
      {
        label: "semantic variants",
        pattern: /neutral|active|success|warning|danger/i,
      },
      { label: "pulse or spin animation", pattern: /pulse|spin/i },
    ],
  },
  {
    filename: "Toast.stories.tsx",
    expectations: [
      {
        label: "semantic variants",
        pattern: /success|danger|warning|info/i,
      },
      { label: "dismiss interaction", pattern: /dismiss|close/i },
    ],
  },
  {
    filename: "Select.stories.tsx",
    expectations: [
      { label: "default/basic usage", pattern: BASIC_USAGE_PATTERN },
      { label: "disabled state", pattern: /disabled/i },
    ],
  },
  {
    filename: "Switch.stories.tsx",
    expectations: [
      { label: "checked or unchecked states", pattern: /checked|on|off/i },
      { label: "disabled state", pattern: /disabled/i },
    ],
  },
  {
    filename: "Checkbox.stories.tsx",
    expectations: [
      { label: "checked state", pattern: /checked/i },
      { label: "indeterminate state", pattern: /indeterminate/i },
      { label: "disabled state", pattern: /disabled/i },
    ],
  },
  {
    filename: "Radio.stories.tsx",
    expectations: [
      { label: "vertical layout", pattern: /vertical/i },
      { label: "horizontal layout", pattern: /horizontal/i },
      { label: "disabled state", pattern: /disabled/i },
    ],
  },
  {
    filename: "Slider.stories.tsx",
    expectations: [
      {
        label: "default/basic usage with a value",
        pattern: /Default|Basic|value/i,
      },
      { label: "disabled state", pattern: /disabled/i },
    ],
  },
  {
    filename: "Table.stories.tsx",
    expectations: [
      { label: "basic/default usage", pattern: BASIC_USAGE_PATTERN },
      { label: "mono value display in cells", pattern: /mono|code/i },
    ],
  },
  {
    filename: "Card.stories.tsx",
    expectations: [
      { label: "basic/default usage", pattern: BASIC_USAGE_PATTERN },
      {
        label: "header and content composition",
        pattern: /CardHeader|CardTitle|CardContent/,
      },
    ],
  },
  {
    filename: "StatCard.stories.tsx",
    expectations: [
      { label: "basic stat display", pattern: BASIC_USAGE_PATTERN },
      { label: "delta/trend badge variant", pattern: /delta|trend|change/i },
    ],
  },
  {
    filename: "CodeBlock.stories.tsx",
    expectations: [
      { label: "basic usage with code content", pattern: BASIC_USAGE_PATTERN },
      { label: "copy button interaction", pattern: /copy|clipboard/i },
    ],
  },
  {
    filename: "Dialog.stories.tsx",
    expectations: [
      { label: "basic/default dialog usage", pattern: BASIC_USAGE_PATTERN },
      {
        label: "footer or actions",
        pattern: /Footer|footer|Action|action|Button|button/,
      },
    ],
  },
  {
    filename: "DropdownMenu.stories.tsx",
    expectations: [
      { label: "basic/default dropdown usage", pattern: BASIC_USAGE_PATTERN },
      {
        label: "separator or groups",
        pattern: /Separator|separator|Group|group|Section|section/,
      },
    ],
  },
  {
    filename: "Command.stories.tsx",
    expectations: [
      {
        label: "basic/default command palette usage",
        pattern: BASIC_USAGE_PATTERN,
      },
      {
        label: "shortcuts",
        pattern: /Shortcut|shortcut|Keyboard|keyboard|hotkey|Hotkey/,
      },
    ],
  },
  {
    filename: "Sheet.stories.tsx",
    expectations: [
      { label: "basic/default sheet usage", pattern: BASIC_USAGE_PATTERN },
      {
        label: "side variants",
        pattern: /right|left|top|bottom|side/i,
      },
    ],
  },
  {
    filename: "Popover.stories.tsx",
    expectations: [
      { label: "basic/default popover usage", pattern: BASIC_USAGE_PATTERN },
      {
        label: "placement or alignment options",
        pattern: /align|side|placement|position|top|bottom|left|right/i,
      },
    ],
  },
  {
    filename: "Tabs.stories.tsx",
    expectations: [
      { label: "basic/default usage", pattern: BASIC_USAGE_PATTERN },
      {
        label: "line or underline variant",
        pattern: /line|underline|default/i,
      },
    ],
  },
  {
    filename: "Breadcrumb.stories.tsx",
    expectations: [
      { label: "basic/default usage", pattern: BASIC_USAGE_PATTERN },
      {
        label: "multi-level breadcrumb path",
        pattern: /multi|level|nested|deep/i,
      },
    ],
  },
  {
    filename: "Pagination.stories.tsx",
    expectations: [
      { label: "basic/default usage", pattern: BASIC_USAGE_PATTERN },
      {
        label: "range display",
        pattern: /range|of\s+\d|total|count/i,
      },
    ],
  },
] as const;

function storyPath(filename: string): string {
  return resolve(STORIES_DIR, filename);
}

function readStory(filename: string): string {
  return readFileSync(storyPath(filename), "utf-8");
}

describe("component story surface", () => {
  it("keeps representative component story files in the package story surface", () => {
    const missingStories = COMPONENT_STORY_SURFACE.filter((filename) => {
      return !existsSync(storyPath(filename));
    });

    expect(missingStories).toEqual([]);
  });

  it.each(COMPONENT_STORY_SURFACE)(
    "%s has minimum Storybook structure",
    (filename) => {
      const source = readStory(filename);

      expect(source).toMatch(/export\s+default\s+/);
      expect(source).toMatch(/\btitle\s*:/);
      expect(source).toMatch(/export\s+const\s+\w+/);
    },
  );

  it.each(COMPONENT_STORY_SCENARIOS)(
    "$filename preserves required scenario story coverage",
    ({ filename, expectations }) => {
      const source = readStory(filename);
      const missingExpectations = expectations.flatMap(({ label, pattern }) => {
        return pattern.test(source) ? [] : [label];
      });

      expect(missingExpectations).toEqual([]);
    },
  );
});
