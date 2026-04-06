import { describe, expect, it } from "vitest";

import {
  REGRESSION_BADGE_CLASSES,
} from "../regressionBadge.styles";

// ---------------------------------------------------------------------------
// AC-5: Badge styling matches spec tokens
// ---------------------------------------------------------------------------

describe("REGRESSION_BADGE_CLASSES", () => {
  it("uses --warning-11 for badge text color", () => {
    expect(REGRESSION_BADGE_CLASSES).toContain("--warning-11");
  });

  it("badge class string is non-empty", () => {
    expect(typeof REGRESSION_BADGE_CLASSES).toBe("string");
    expect(REGRESSION_BADGE_CLASSES.length).toBeGreaterThan(0);
  });
});
