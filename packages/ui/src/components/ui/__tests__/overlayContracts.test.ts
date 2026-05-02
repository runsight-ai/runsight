/**
 * Governance: packages/ui overlay contracts stay with this owner suite.
 * Owner: packages/ui Dialog, DropdownMenu, Command, Sheet, and Popover contracts.
 * Boundary: source-text checks for overlay surfaces, elevation, borders,
 * sizing, motion, stacking, and typography under src/components/ui only.
 * Exit criteria: keep one table per contract row and promote new shared
 * overlay coverage here.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const UI_DIR = resolve(__dirname, "..");

type ContractRow = {
  component: "Dialog" | "DropdownMenu" | "Command" | "Sheet" | "Popover";
  filename: string;
  behavior: string;
  pattern: RegExp;
};

export const OVERLAY_CONTRACTS: ContractRow[] = [
  {
    component: "Dialog",
    filename: "dialog.tsx",
    behavior: "content background uses an overlay surface token",
    pattern: /surface-overlay|elevation-overlay-surface/,
  },
  {
    component: "Dialog",
    filename: "dialog.tsx",
    behavior: "content shadow uses the overlay shadow token",
    pattern: /elevation-overlay-shadow/,
  },
  {
    component: "Dialog",
    filename: "dialog.tsx",
    behavior: "content border uses the raised elevation border token",
    pattern: /elevation-border-raised/,
  },
  {
    component: "Dialog",
    filename: "dialog.tsx",
    behavior: "title text uses the heading text token",
    pattern: /text-heading/,
  },
  {
    component: "Dialog",
    filename: "dialog.tsx",
    behavior: "title size uses the large font token",
    pattern: /font-size-lg|text-lg/,
  },
  {
    component: "Dialog",
    filename: "dialog.tsx",
    behavior: "content width uses the medium overlay width token",
    pattern: /overlay-width-md/,
  },
  {
    component: "Dialog",
    filename: "dialog.tsx",
    behavior: "open animation uses the scale animation token",
    pattern: /scale-in/,
  },
  {
    component: "DropdownMenu",
    filename: "dropdown-menu.tsx",
    behavior: "separator uses the subtle border token",
    pattern: /border-subtle/,
  },
  {
    component: "DropdownMenu",
    filename: "dropdown-menu.tsx",
    behavior: "items use small icons or icon affordances",
    pattern: /icon-size-sm|size-4|ChevronRightIcon|CheckIcon|lucide/,
  },
  {
    component: "DropdownMenu",
    filename: "dropdown-menu.tsx",
    behavior: "positioner uses the dropdown stack token",
    pattern: /z-dropdown/,
  },
  {
    component: "Command",
    filename: "command.tsx",
    behavior: "palette uses the modal stack token",
    pattern: /z-modal/,
  },
  {
    component: "Command",
    filename: "command.tsx",
    behavior: "shortcut badge uses the mono font token",
    pattern: /font-mono/,
  },
  {
    component: "Command",
    filename: "command.tsx",
    behavior: "shortcut badge size uses the extra extra small font token",
    pattern: /font-size-2xs|text-2xs/,
  },
  {
    component: "Sheet",
    filename: "sheet.tsx",
    behavior: "content background uses an overlay surface token",
    pattern: /surface-overlay|elevation-overlay-surface/,
  },
  {
    component: "Sheet",
    filename: "sheet.tsx",
    behavior: "content shadow uses the overlay shadow token",
    pattern: /elevation-overlay-shadow/,
  },
  {
    component: "Sheet",
    filename: "sheet.tsx",
    behavior: "transition uses a design-system motion token",
    pattern:
      /duration-overlay|duration-slow|duration-fast|duration-medium|ease-overlay|ease-smooth|ease-spring|var\(--duration/,
  },
  {
    component: "Popover",
    filename: "popover.tsx",
    behavior: "content background uses a raised or overlay surface token",
    pattern: /surface-raised|elevation-overlay-surface/,
  },
  {
    component: "Popover",
    filename: "popover.tsx",
    behavior: "content shadow uses a raised or overlay shadow token",
    pattern: /elevation-raised-shadow|elevation-overlay-shadow/,
  },
  {
    component: "Popover",
    filename: "popover.tsx",
    behavior: "content border uses the raised elevation border token",
    pattern: /elevation-border-raised/,
  },
];

function readComponent(filename: string): string {
  return readFileSync(resolve(UI_DIR, filename), "utf-8");
}

describe("overlay component contracts", () => {
  it.each(OVERLAY_CONTRACTS)("$component $behavior", ({ filename, pattern }) => {
    expect(readComponent(filename)).toMatch(pattern);
  });
});
