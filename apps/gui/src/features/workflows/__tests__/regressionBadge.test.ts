import { describe, expect, it } from "vitest";

import {
  formatRegressionTooltip,
  shouldShowRegressionBadge,
  buildRunsFilterUrl,
} from "../regressionBadge.utils";
import type { WorkflowRegression } from "../../../types/schemas/regressions";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const REGRESSIONS_MULTI: WorkflowRegression[] = [
  { type: "assertion", node_name: "Quality Review" },
  { type: "cost_spike", node_name: "Writer", delta_pct: 34 },
];

const REGRESSIONS_SINGLE: WorkflowRegression[] = [
  { type: "latency_spike", node_name: "Summarizer", delta_pct: 120 },
];

const REGRESSIONS_EMPTY: WorkflowRegression[] = [];

// ---------------------------------------------------------------------------
// AC-4: Badge and tooltip hidden when 0 regressions
// ---------------------------------------------------------------------------

describe("shouldShowRegressionBadge", () => {
  it("returns false when regressions array is empty", () => {
    expect(shouldShowRegressionBadge(REGRESSIONS_EMPTY)).toBe(false);
  });

  it("returns false when regressions is undefined", () => {
    expect(shouldShowRegressionBadge(undefined)).toBe(false);
  });

  it("returns true when at least one regression exists", () => {
    expect(shouldShowRegressionBadge(REGRESSIONS_SINGLE)).toBe(true);
  });

  it("returns true for multiple regressions", () => {
    expect(shouldShowRegressionBadge(REGRESSIONS_MULTI)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// AC-2: Tooltip lists per-issue regression summary (type + node name)
// ---------------------------------------------------------------------------

describe("formatRegressionTooltip", () => {
  it("includes count header matching regressions length", () => {
    const result = formatRegressionTooltip(REGRESSIONS_MULTI);
    expect(result.header).toBe("2 regressions");
  });

  it("uses singular 'regression' for count of 1", () => {
    const result = formatRegressionTooltip(REGRESSIONS_SINGLE);
    expect(result.header).toBe("1 regression");
  });

  it("produces one summary line per regression with type and node name", () => {
    const result = formatRegressionTooltip(REGRESSIONS_MULTI);
    expect(result.lines).toHaveLength(2);
    // First line: assertion type with node name
    expect(result.lines[0]).toContain("Assertion");
    expect(result.lines[0]).toContain("Quality Review");
    // Second line: cost spike with delta
    expect(result.lines[1]).toContain("Cost spike");
    expect(result.lines[1]).toContain("Writer");
    expect(result.lines[1]).toContain("+34%");
  });

  it("formats latency_spike type with delta percentage", () => {
    const result = formatRegressionTooltip(REGRESSIONS_SINGLE);
    expect(result.lines[0]).toContain("Latency spike");
    expect(result.lines[0]).toContain("Summarizer");
    expect(result.lines[0]).toContain("+120%");
  });

  it("returns empty lines array for no regressions", () => {
    const result = formatRegressionTooltip(REGRESSIONS_EMPTY);
    expect(result.header).toBe("0 regressions");
    expect(result.lines).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// AC-3: "View runs →" CTA navigates to /runs?workflow=:id
// ---------------------------------------------------------------------------

describe("buildRunsFilterUrl", () => {
  it("builds correct URL with workflow id query param", () => {
    const url = buildRunsFilterUrl("wf-abc-123");
    expect(url).toBe("/runs?workflow=wf-abc-123");
  });

  it("encodes special characters in workflow id", () => {
    const url = buildRunsFilterUrl("wf/special&id");
    expect(url).toContain("/runs?workflow=");
    // The id should be URI-encoded
    expect(url).not.toContain("&id");
  });
});
