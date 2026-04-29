/**
 * Governance: dashboard polling configuration boundary.
 *
 * Owner: GUI Dashboard data hooks.
 * Boundary: dashboard refresh stays in React Query polling options, not
 * ad-hoc timers inside dashboard feature code.
 * Exit criteria: replace with query-option contract helpers or lint rules once
 * polling policies are centralized.
 *
 * Validates that React Query polling is configured correctly:
 *  - useDashboardKPIs: refetchInterval 30 000 ms, background polling off
 *  - useActiveRuns:    background polling off
 *  - No manual setInterval / setTimeout used for polling
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const guiSrc = resolve(__dirname, "../../..");

function readSource(relPath: string): string {
  return readFileSync(resolve(guiSrc, relPath), "utf-8");
}

const dashboardSource = readSource("queries/dashboard.ts");
const runsSource = readSource("queries/runs.ts");

/* ------------------------------------------------------------------ */
/*  useDashboardKPIs — 30 s polling                                    */
/* ------------------------------------------------------------------ */

describe("Governance: dashboard polling configuration boundary", () => {
  it("sets refetchInterval to 30 000 ms", () => {
    // The useQuery options object inside useDashboardKPIs must contain
    // refetchInterval: 30000 (or 30_000).
    const hasInterval = /refetchInterval\s*:\s*30[_]?000/.test(dashboardSource);
    expect(hasInterval).toBe(true);
  });

  it("disables background polling (refetchIntervalInBackground: false)", () => {
    const hasBackground = /refetchIntervalInBackground\s*:\s*false/.test(
      dashboardSource,
    );
    expect(hasBackground).toBe(true);
  });
  it("disables background polling (refetchIntervalInBackground: false)", () => {
    // useActiveRuns must explicitly opt out of background polling.
    // Active runs polling already has its interval; this check protects
    // the background polling requirement.
    const hasBackground = /refetchIntervalInBackground\s*:\s*false/.test(
      runsSource,
    );
    expect(hasBackground).toBe(true);
  });
  it("dashboard.ts does not use setInterval", () => {
    expect(dashboardSource).not.toMatch(/setInterval/);
  });

  it("dashboard.ts does not use setTimeout for polling", () => {
    expect(dashboardSource).not.toMatch(/setTimeout/);
  });

  it("runs.ts does not use setInterval", () => {
    expect(runsSource).not.toMatch(/setInterval/);
  });

  it("runs.ts does not use setTimeout for polling", () => {
    expect(runsSource).not.toMatch(/setTimeout/);
  });
});
