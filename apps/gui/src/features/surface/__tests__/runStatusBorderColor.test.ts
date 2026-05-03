import { beforeEach, describe, expect, it } from "vitest";

import type { getStatusBorderColor as GetStatusBorderColorFn } from "../useRunStream";

describe("run status border color", () => {
  let getStatusBorderColor: typeof GetStatusBorderColorFn;

  beforeEach(async () => {
    const mod = await import("../useRunStream");
    getStatusBorderColor = mod.getStatusBorderColor;
  });

  it("uses default border styling for idle, pending, and paused statuses", () => {
    for (const status of ["idle", "pending", "paused"] as const) {
      const result = getStatusBorderColor(status);

      expect(result).toContain("border");
      expect(result).not.toMatch(/blue|green|red/i);
    }
  });

  it("uses distinct active border styling for running, completed, and failed statuses", () => {
    const running = getStatusBorderColor("running");
    const completed = getStatusBorderColor("completed");
    const failed = getStatusBorderColor("failed");

    expect(running).toMatch(/blue/i);
    expect(completed).toMatch(/green/i);
    expect(failed).toMatch(/red/i);
    expect(new Set([running, completed, failed]).size).toBe(3);
  });

  it("returns stable values for repeated status lookups", () => {
    expect(getStatusBorderColor("running")).toBe(getStatusBorderColor("running"));
  });
});
