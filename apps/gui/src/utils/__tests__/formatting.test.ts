import { describe, it, expect } from "vitest";
import {
  formatDuration,
  truncateText,
  formatTimestamp,
  formatCost,
  getTimeAgo,
} from "../formatting";

// ---------------------------------------------------------------------------
// formatDuration
// ---------------------------------------------------------------------------
describe("formatDuration", () => {
  it("returns em-dash for null", () => {
    expect(formatDuration(null)).toBe("\u2014");
  });

  it("returns em-dash for undefined", () => {
    expect(formatDuration(undefined)).toBe("\u2014");
  });

  it("returns em-dash for 0", () => {
    expect(formatDuration(0)).toBe("\u2014");
  });

  it("returns em-dash for negative numbers", () => {
    expect(formatDuration(-10)).toBe("\u2014");
  });

  it("formats seconds only when under 60s", () => {
    expect(formatDuration(45)).toBe("45s");
  });

  it("formats 1 second", () => {
    expect(formatDuration(1)).toBe("1s");
  });

  it("formats 59 seconds", () => {
    expect(formatDuration(59)).toBe("59s");
  });

  it("formats exact minutes with no remaining seconds", () => {
    expect(formatDuration(120)).toBe("2m");
  });

  it("formats minutes and seconds", () => {
    expect(formatDuration(154)).toBe("2m 34s");
  });

  it("rounds fractional seconds to a whole second", () => {
    expect(formatDuration(53.92472696304321)).toBe("54s");
  });

  it("pads seconds to two digits when minutes are shown", () => {
    expect(formatDuration(125)).toBe("2m 05s");
  });

  it("formats exactly 60 seconds as 1m", () => {
    expect(formatDuration(60)).toBe("1m");
  });

  it("formats hours and minutes", () => {
    expect(formatDuration(3661)).toBe("1h 1m");
  });

  it("formats exact hours with no remaining minutes", () => {
    expect(formatDuration(3600)).toBe("1h");
  });

  it("formats multiple hours", () => {
    expect(formatDuration(7200)).toBe("2h");
  });

  it("formats hours with remaining minutes", () => {
    expect(formatDuration(5400)).toBe("1h 30m");
  });
});

// ---------------------------------------------------------------------------
// truncateText
// ---------------------------------------------------------------------------
describe("truncateText", () => {
  it("returns em-dash for null", () => {
    expect(truncateText(null, 10)).toBe("\u2014");
  });

  it("returns em-dash for undefined", () => {
    expect(truncateText(undefined, 10)).toBe("\u2014");
  });

  it("returns em-dash for empty string", () => {
    expect(truncateText("", 10)).toBe("\u2014");
  });

  it("returns text as-is when under maxLength", () => {
    expect(truncateText("hello", 10)).toBe("hello");
  });

  it("returns text as-is when exactly at maxLength", () => {
    expect(truncateText("hello", 5)).toBe("hello");
  });

  it("truncates and adds ellipsis when over maxLength", () => {
    expect(truncateText("hello world", 5)).toBe("hello...");
  });

  it("truncates to maxLength of 1", () => {
    expect(truncateText("abc", 1)).toBe("a...");
  });

  it("handles single character text under limit", () => {
    expect(truncateText("a", 5)).toBe("a");
  });
});

// ---------------------------------------------------------------------------
// formatTimestamp
// ---------------------------------------------------------------------------
describe("formatTimestamp", () => {
  it("returns em-dash for null", () => {
    expect(formatTimestamp(null)).toBe("\u2014");
  });

  it("returns em-dash for undefined", () => {
    expect(formatTimestamp(undefined)).toBe("\u2014");
  });

  it("returns em-dash for 0", () => {
    expect(formatTimestamp(0)).toBe("\u2014");
  });

  it("formats a unix epoch timestamp (seconds) into human-readable date", () => {
    // 1700000000 = Nov 14, 2023 at some time
    const result = formatTimestamp(1700000000);
    // Should contain month and day at minimum
    expect(result).toContain("Nov");
    expect(result).toContain("14");
  });

  it("returns a string containing hour and minute components", () => {
    const result = formatTimestamp(1700000000);
    // The toLocaleString format includes hour:minute
    expect(result).toMatch(/\d{1,2}:\d{2}/);
  });

  it("treats timestamp as seconds not milliseconds", () => {
    // If treated as ms, 1700000 would be Jan 1970; as seconds it's Jan 20, 1970
    const result = formatTimestamp(1700000000);
    // Should NOT be in 1970
    expect(result).not.toContain("1970");
  });
});

// ---------------------------------------------------------------------------
// formatCost
// ---------------------------------------------------------------------------
describe("formatCost", () => {
  it("returns em-dash for null", () => {
    expect(formatCost(null)).toBe("\u2014");
  });

  it("returns em-dash for undefined", () => {
    expect(formatCost(undefined)).toBe("\u2014");
  });

  it("formats zero cost", () => {
    expect(formatCost(0)).toBe("$0.000");
  });

  it("formats cost with 3 decimal places", () => {
    expect(formatCost(1.5)).toBe("$1.500");
  });

  it("formats small cost values", () => {
    expect(formatCost(0.001)).toBe("$0.001");
  });

  it("formats cost and rounds to 3 decimals", () => {
    expect(formatCost(0.12345)).toBe("$0.123");
  });

  it("formats integer cost with decimals", () => {
    expect(formatCost(42)).toBe("$42.000");
  });

  it("formats sub-milli-cent cost values with more precision", () => {
    expect(formatCost(0.0001132)).toBe("$0.000113");
  });
});

// ---------------------------------------------------------------------------
// getTimeAgo
// ---------------------------------------------------------------------------
describe("getTimeAgo", () => {
  it("returns em-dash for undefined", () => {
    expect(getTimeAgo(undefined)).toBe("\u2014");
  });

  it("returns 'just now' for a date less than a minute ago", () => {
    const now = new Date().toISOString();
    expect(getTimeAgo(now)).toBe("just now");
  });

  it("returns minutes ago for dates within the last hour", () => {
    const fiveMinAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    expect(getTimeAgo(fiveMinAgo)).toBe("5 min ago");
  });

  it("returns singular hour for 1 hour ago", () => {
    const oneHourAgo = new Date(Date.now() - 61 * 60 * 1000).toISOString();
    expect(getTimeAgo(oneHourAgo)).toBe("1 hour ago");
  });

  it("returns plural hours for multiple hours ago", () => {
    const threeHoursAgo = new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString();
    expect(getTimeAgo(threeHoursAgo)).toBe("3 hours ago");
  });

  it("returns days ago for dates within the last week", () => {
    const twoDaysAgo = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString();
    expect(getTimeAgo(twoDaysAgo)).toBe("2 days ago");
  });

  it("returns weeks ago for dates within the last month", () => {
    const twoWeeksAgo = new Date(Date.now() - 14 * 24 * 60 * 60 * 1000).toISOString();
    expect(getTimeAgo(twoWeeksAgo)).toBe("2 weeks ago");
  });

  it("returns locale date string for dates older than 4 weeks", () => {
    const oldDate = new Date(Date.now() - 60 * 24 * 60 * 60 * 1000).toISOString();
    const result = getTimeAgo(oldDate);
    // Should not contain "ago" — it falls back to toLocaleDateString
    expect(result).not.toContain("ago");
    expect(result).not.toBe("\u2014");
  });
});
