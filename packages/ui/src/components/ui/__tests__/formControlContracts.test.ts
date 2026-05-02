/**
 * Governance: packages/ui form control contracts stay with this owner suite.
 * Owner: packages/ui Select, Switch, Checkbox, Radio, and Slider contracts.
 * Boundary: source-text checks for component files, exports, tokens, states,
 * layout, and accessibility hooks under src/components/ui only.
 * Exit criteria: keep one table per contract row and promote new shared form
 * control coverage here.
 */

import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const UI_DIR = resolve(__dirname, "..");

type ContractRow = {
  component: "Select" | "Switch" | "Checkbox" | "Radio" | "Slider";
  filename: string;
  behavior: string;
  pattern: RegExp;
  absent?: boolean;
  requiresFile?: boolean;
};

export const FORM_CONTROL_CONTRACTS: ContractRow[] = [
  {
    component: "Select",
    filename: "select.tsx",
    behavior: "trigger height uses the small control height token",
    pattern: /control-height-sm/,
  },
  {
    component: "Select",
    filename: "select.tsx",
    behavior: "trigger border uses the default border token",
    pattern: /border-default/,
  },
  {
    component: "Select",
    filename: "select.tsx",
    behavior: "trigger hover border uses the hover border token",
    pattern: /border-hover/,
  },
  {
    component: "Select",
    filename: "select.tsx",
    behavior: "trigger background uses the tertiary surface token",
    pattern: /surface-tertiary/,
  },
  {
    component: "Select",
    filename: "select.tsx",
    behavior: "dropdown background uses the overlay surface token",
    pattern: /surface-overlay/,
  },
  {
    component: "Select",
    filename: "select.tsx",
    behavior: "selected value text uses the primary text token",
    pattern: /text-primary/,
  },
  {
    component: "Select",
    filename: "select.tsx",
    behavior: "dropdown elevation uses the overlay shadow token",
    pattern: /elevation-overlay-shadow|shadow-overlay/,
  },
  {
    component: "Switch",
    filename: "switch.tsx",
    behavior: "unchecked track uses a neutral token",
    pattern: /neutral-5|neutral-6/,
  },
  {
    component: "Switch",
    filename: "switch.tsx",
    behavior: "checked track uses the default interactive token",
    pattern: /interactive-default/,
  },
  {
    component: "Switch",
    filename: "switch.tsx",
    behavior: "thumb uses the light neutral token",
    pattern: /neutral-12/,
  },
  {
    component: "Switch",
    filename: "switch.tsx",
    behavior: "unchecked track has replaced the old input background",
    pattern: /data-unchecked:bg-input\b/,
    absent: true,
  },
  {
    component: "Checkbox",
    filename: "checkbox.tsx",
    behavior: "component file exists",
    pattern: /./,
    requiresFile: true,
  },
  {
    component: "Checkbox",
    filename: "checkbox.tsx",
    behavior: "exports Checkbox",
    pattern: /export.*\bCheckbox\b/,
  },
  {
    component: "Checkbox",
    filename: "checkbox.tsx",
    behavior: "checked state uses the default interactive token",
    pattern: /interactive-default/,
  },
  {
    component: "Checkbox",
    filename: "checkbox.tsx",
    behavior: "unchecked border uses the default border token",
    pattern: /border-default/,
  },
  {
    component: "Checkbox",
    filename: "checkbox.tsx",
    behavior: "unchecked background uses the primary surface token",
    pattern: /surface-primary/,
  },
  {
    component: "Checkbox",
    filename: "checkbox.tsx",
    behavior: "shape uses the extra small radius token",
    pattern: /radius-xs|rounded-xs/,
  },
  {
    component: "Checkbox",
    filename: "checkbox.tsx",
    behavior: "supports an indeterminate state",
    pattern: /indeterminate/,
  },
  {
    component: "Checkbox",
    filename: "checkbox.tsx",
    behavior: "supports a disabled state",
    pattern: /disabled/,
  },
  {
    component: "Checkbox",
    filename: "checkbox.tsx",
    behavior: "uses a native checkbox input or checkbox role",
    pattern: /type\s*=\s*["']checkbox["']|role\s*=\s*["']checkbox["']/,
  },
  {
    component: "Radio",
    filename: "radio.tsx",
    behavior: "component file exists",
    pattern: /./,
    requiresFile: true,
  },
  {
    component: "Radio",
    filename: "radio.tsx",
    behavior: "exports Radio",
    pattern: /export.*\bRadio\b/,
  },
  {
    component: "Radio",
    filename: "radio.tsx",
    behavior: "selected state uses the default interactive token",
    pattern: /interactive-default/,
  },
  {
    component: "Radio",
    filename: "radio.tsx",
    behavior: "unselected border uses the default border token",
    pattern: /border-default/,
  },
  {
    component: "Radio",
    filename: "radio.tsx",
    behavior: "shape uses the full radius token",
    pattern: /radius-full/,
  },
  {
    component: "Radio",
    filename: "radio.tsx",
    behavior: "unselected background uses the primary surface token",
    pattern: /surface-primary/,
  },
  {
    component: "Radio",
    filename: "radio.tsx",
    behavior: "supports vertical layout",
    pattern: /vertical|flex-col|RadioGroup/,
  },
  {
    component: "Radio",
    filename: "radio.tsx",
    behavior: "supports horizontal layout",
    pattern: /horizontal|flex-row|inline-flex/,
  },
  {
    component: "Radio",
    filename: "radio.tsx",
    behavior: "supports a disabled state",
    pattern: /disabled/,
  },
  {
    component: "Radio",
    filename: "radio.tsx",
    behavior: "uses a native radio input or radio role",
    pattern: /type\s*=\s*["']radio["']|role\s*=\s*["']radio["']/,
  },
  {
    component: "Slider",
    filename: "slider.tsx",
    behavior: "component file exists",
    pattern: /./,
    requiresFile: true,
  },
  {
    component: "Slider",
    filename: "slider.tsx",
    behavior: "exports Slider",
    pattern: /export.*\bSlider\b/,
  },
  {
    component: "Slider",
    filename: "slider.tsx",
    behavior: "track background uses a tertiary surface or neutral token",
    pattern: /surface-tertiary|neutral-5/,
  },
  {
    component: "Slider",
    filename: "slider.tsx",
    behavior: "filled portion uses the default interactive token",
    pattern: /interactive-default/,
  },
  {
    component: "Slider",
    filename: "slider.tsx",
    behavior: "thumb background uses a light neutral or primary surface token",
    pattern: /neutral-12|surface-primary/,
  },
  {
    component: "Slider",
    filename: "slider.tsx",
    behavior: "thumb elevation uses the raised shadow token",
    pattern: /elevation-raised-shadow|shadow-raised/,
  },
  {
    component: "Slider",
    filename: "slider.tsx",
    behavior: "thumb shape uses the full radius token",
    pattern: /radius-full/,
  },
  {
    component: "Slider",
    filename: "slider.tsx",
    behavior: "uses a native range input or slider role",
    pattern: /type\s*=\s*["']range["']|role\s*=\s*["']slider["']/,
  },
];

function componentPath(filename: string): string {
  return resolve(UI_DIR, filename);
}

function readComponent(filename: string): string {
  return readFileSync(componentPath(filename), "utf-8");
}

describe("form control component contracts", () => {
  it.each(FORM_CONTROL_CONTRACTS)(
    "$component $behavior",
    ({ filename, pattern, absent, requiresFile }) => {
      const path = componentPath(filename);

      if (requiresFile) {
        expect(existsSync(path)).toBe(true);
        return;
      }

      const source = readComponent(filename);
      const assertion = expect(source);

      if (absent) {
        assertion.not.toMatch(pattern);
        return;
      }

      assertion.toMatch(pattern);
    },
  );
});
