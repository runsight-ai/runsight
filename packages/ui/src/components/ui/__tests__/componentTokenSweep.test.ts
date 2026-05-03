import { describe, expect, it } from "vitest";
import { badgeVariants } from "../badge";
import { buttonVariants } from "../button";

/**
 * Governance: component token coverage is now adapter smoke, not a full source
 * sweep of every class token.
 * Owner: packages/ui design-system maintainers.
 * Boundary: public CVA adapters that package consumers use directly.
 * Exit criteria: remove this once variant adapters have dedicated type-level
 * or package export contract coverage.
 */

const LEGACY_SHADCN_CLASS_ALIASES = [
  "bg-background",
  "bg-card",
  "text-muted-foreground",
  "border-input",
  "ring-ring",
] as const;

export const COMPONENT_TOKEN_ADAPTER_SMOKE = [
  {
    label: "button primary",
    classes: () => buttonVariants({ variant: "primary", size: "sm" }),
  },
  {
    label: "button icon-only",
    classes: () => buttonVariants({ variant: "icon-only", size: "icon-sm" }),
  },
  {
    label: "badge success",
    classes: () => badgeVariants({ variant: "success" }),
  },
] as const;

describe("component token adapter smoke", () => {
  it.each(COMPONENT_TOKEN_ADAPTER_SMOKE)(
    "$label returns a non-empty public class contract",
    ({ classes }) => {
      expect(classes()).toEqual(expect.any(String));
      expect(classes().length).toBeGreaterThan(0);
    },
  );

  it("representative public adapters avoid old shadcn aliases", () => {
    const adapterOutput = COMPONENT_TOKEN_ADAPTER_SMOKE.map(({ classes }) => classes()).join(" ");

    for (const legacyAlias of LEGACY_SHADCN_CLASS_ALIASES) {
      expect(adapterOutput).not.toContain(legacyAlias);
    }
  });
});
