/**
 * Red tests for RUN-345: Dashboard auto-refresh polling
 *
 * Validates that React Query polling is configured correctly:
 *  - useDashboardKPIs: refetchInterval 30 000 ms, background polling off
 *  - useActiveRuns:    refetchInterval  5 000 ms, background polling off
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

describe("useDashboardKPIs auto-refresh", () => {
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
});

/* ------------------------------------------------------------------ */
/*  useActiveRuns — 5 s polling                                        */
/* ------------------------------------------------------------------ */

describe("useActiveRuns auto-refresh", () => {
  it("sets refetchInterval to 5 000 ms", () => {
    const hasInterval = /refetchInterval\s*:\s*5[_]?000/.test(runsSource);
    expect(hasInterval).toBe(true);
  });

  it("disables background polling (refetchIntervalInBackground: false)", () => {
    // useActiveRuns must explicitly opt out of background polling.
    const hasBackground = /refetchIntervalInBackground\s*:\s*false/.test(
      runsSource,
    );
    expect(hasBackground).toBe(true);
  });
});

/* ------------------------------------------------------------------ */
/*  No custom polling logic                                            */
/* ------------------------------------------------------------------ */

describe("no custom polling logic", () => {
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
