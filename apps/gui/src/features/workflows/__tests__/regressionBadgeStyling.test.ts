import { describe, expect, it } from "vitest";

import {
  REGRESSION_BADGE_CLASSES,
  REGRESSION_TOOLTIP_CLASSES,
} from "../regressionBadge.styles";

// ---------------------------------------------------------------------------
// AC-5: Tooltip styling matches spec tokens
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

describe("REGRESSION_TOOLTIP_CLASSES", () => {
  it("uses --surface-elevated background token", () => {
    expect(REGRESSION_TOOLTIP_CLASSES).toContain("--surface-elevated");
  });

  it("uses --border-subtle border token", () => {
    expect(REGRESSION_TOOLTIP_CLASSES).toContain("--border-subtle");
  });

  it("uses radius-md for border radius", () => {
    expect(REGRESSION_TOOLTIP_CLASSES).toContain("radius-md");
  });

  it("uses shadow-md for drop shadow", () => {
    expect(REGRESSION_TOOLTIP_CLASSES).toContain("shadow-md");
  });
});
