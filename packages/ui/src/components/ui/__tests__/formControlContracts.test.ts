/**
 * Governance: packages/ui form control contracts stay with this owner suite.
 * Owner: packages/ui Select, Switch, Checkbox, Radio, Slider, and TagInput
 * contracts.
 * Boundary: public component exports only; rendered states, keyboard paths,
 * and TagInput behavior belong to rendered form-control owners.
 * Exit criteria: keep this smoke until package exports are validated by a
 * generated manifest or type-contract owner.
 */

import { describe, expect, it } from "vitest";
import { Checkbox } from "../checkbox";
import { Radio, RadioGroup } from "../radio";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectScrollDownButton,
  SelectScrollUpButton,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "../select";
import { Slider } from "../slider";
import { Switch } from "../switch";
import { TagInput } from "../tag-input";

type ExportSmoke = {
  component: "Select" | "Switch" | "Checkbox" | "Radio" | "Slider" | "TagInput";
  publicExports: Array<readonly [string, unknown]>;
};

export const FORM_CONTROL_CONTRACTS: ExportSmoke[] = [
  {
    component: "Select",
    publicExports: [
      ["Select", Select],
      ["SelectContent", SelectContent],
      ["SelectGroup", SelectGroup],
      ["SelectItem", SelectItem],
      ["SelectLabel", SelectLabel],
      ["SelectScrollDownButton", SelectScrollDownButton],
      ["SelectScrollUpButton", SelectScrollUpButton],
      ["SelectSeparator", SelectSeparator],
      ["SelectTrigger", SelectTrigger],
      ["SelectValue", SelectValue],
    ],
  },
  { component: "Switch", publicExports: [["Switch", Switch]] },
  { component: "Checkbox", publicExports: [["Checkbox", Checkbox]] },
  {
    component: "Radio",
    publicExports: [
      ["Radio", Radio],
      ["RadioGroup", RadioGroup],
    ],
  },
  { component: "Slider", publicExports: [["Slider", Slider]] },
  { component: "TagInput", publicExports: [["TagInput", TagInput]] },
];

describe("form control public contract smoke", () => {
  it.each(FORM_CONTROL_CONTRACTS)(
    "$component keeps expected public exports defined",
    ({ publicExports }) => {
      for (const [name, value] of publicExports) {
        expect(value, `${name} should remain exported`).toBeDefined();
      }
    },
  );
});
