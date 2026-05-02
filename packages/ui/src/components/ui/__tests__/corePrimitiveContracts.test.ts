import { describe, expect, it } from "vitest";
import { Badge, BadgeDot, badgeVariants } from "../badge";
import { Button, buttonVariants } from "../button";
import { Input } from "../input";
import { Label } from "../label";
import { Textarea } from "../textarea";
import {
  SoulTip,
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../tooltip";

/**
 * Governance: packages/ui core primitive contract coverage stays in a compact
 * public export and adapter smoke suite.
 * Owner: packages/ui design-system primitives for Button, Badge, Input,
 * Textarea, Label, and Tooltip.
 * Boundary: public component exports and CVA adapter keys only; rendered
 * behavior belongs to rendered owner suites.
 * Exit criteria: keep this suite until package exports and variant adapters
 * are covered by generated API/type contract checks.
 */

type ExportSmoke = {
  component: string;
  publicExports: Array<readonly [string, unknown]>;
};

export const CORE_PRIMITIVE_CONTRACTS: ExportSmoke[] = [
  {
    component: "Button",
    publicExports: [
      ["Button", Button],
      ["buttonVariants", buttonVariants],
    ],
  },
  {
    component: "Badge",
    publicExports: [
      ["Badge", Badge],
      ["BadgeDot", BadgeDot],
      ["badgeVariants", badgeVariants],
    ],
  },
  {
    component: "Input",
    publicExports: [["Input", Input]],
  },
  {
    component: "Textarea",
    publicExports: [["Textarea", Textarea]],
  },
  {
    component: "Label",
    publicExports: [["Label", Label]],
  },
  {
    component: "Tooltip",
    publicExports: [
      ["Tooltip", Tooltip],
      ["TooltipTrigger", TooltipTrigger],
      ["TooltipContent", TooltipContent],
      ["TooltipProvider", TooltipProvider],
      ["SoulTip", SoulTip],
    ],
  },
];

describe("core primitive public contract smoke", () => {
  it.each(CORE_PRIMITIVE_CONTRACTS)(
    "$component keeps expected public exports defined",
    ({ publicExports }) => {
      for (const [name, value] of publicExports) {
        expect(value, `${name} should remain exported`).toBeDefined();
      }
    },
  );

  it("keeps Button and Badge semantic variant adapters callable", () => {
    const buttonClasses = [
      buttonVariants({ variant: "primary", size: "sm" }),
      buttonVariants({ variant: "secondary", size: "sm" }),
      buttonVariants({ variant: "ghost", size: "sm" }),
      buttonVariants({ variant: "danger", size: "sm" }),
      buttonVariants({ variant: "icon-only", size: "icon-sm" }),
    ];
    const badgeClasses = [
      badgeVariants({ variant: "accent" }),
      badgeVariants({ variant: "success" }),
      badgeVariants({ variant: "warning" }),
      badgeVariants({ variant: "danger" }),
      badgeVariants({ variant: "info" }),
      badgeVariants({ variant: "neutral" }),
      badgeVariants({ variant: "outline" }),
    ];

    expect(new Set(buttonClasses).size).toBe(buttonClasses.length);
    expect(new Set(badgeClasses).size).toBe(badgeClasses.length);
  });
});
