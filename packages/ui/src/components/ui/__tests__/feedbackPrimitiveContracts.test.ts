import { describe, expect, it } from "vitest";
import { Progress } from "../progress";
import { Skeleton } from "../skeleton";
import { Spinner } from "../spinner";
import { StatusDot } from "../status-dot";
import { Toast } from "../toast";

/**
 * Governance: packages/ui feedback primitive contract coverage stays in a
 * compact public export smoke suite.
 * Owner: packages/ui design-system primitives for Spinner, Skeleton, Progress,
 * StatusDot, and Toast.
 * Boundary: public component exports only; rendered roles, states, and
 * animation behavior belong to rendered owner suites.
 * Exit criteria: keep this suite until package exports are validated by a
 * generated manifest or type-contract owner.
 */

type ExportSmoke = {
  component: "Spinner" | "Skeleton" | "Progress" | "StatusDot" | "Toast";
  publicExports: Array<readonly [string, unknown]>;
};

export const FEEDBACK_PRIMITIVE_CONTRACTS: ExportSmoke[] = [
  { component: "Spinner", publicExports: [["Spinner", Spinner]] },
  { component: "Skeleton", publicExports: [["Skeleton", Skeleton]] },
  { component: "Progress", publicExports: [["Progress", Progress]] },
  { component: "StatusDot", publicExports: [["StatusDot", StatusDot]] },
  { component: "Toast", publicExports: [["Toast", Toast]] },
];

describe("feedback primitive public contract smoke", () => {
  it.each(FEEDBACK_PRIMITIVE_CONTRACTS)(
    "$component keeps expected public exports defined",
    ({ publicExports }) => {
      for (const [name, value] of publicExports) {
        expect(value, `${name} should remain exported`).toBeDefined();
      }
    },
  );
});
