/**
 * Governance for source-level API client parsing and dashboard query wiring.
 *
 * Boundary: GUI API client adapters and dashboard query adapter.
 * Owner: GUI API tests until the source-level guards are replaced by behavior
 * tests around the generated shared contracts and fetch adapters.
 * Exit criteria: delete this suite once adapter behavior tests prove response
 * parsing and query delegation without implementation-source inspection.
 */

import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const workflowsSource = readFileSync(new URL("../workflows.ts", import.meta.url), "utf8");
const runsSource = readFileSync(new URL("../runs.ts", import.meta.url), "utf8");
const dashboardQuerySource = readFileSync(
  new URL("../../queries/dashboard.ts", import.meta.url),
  "utf8",
);
const gitSource = readFileSync(new URL("../git.ts", import.meta.url), "utf8");

describe("API client parsing governance", () => {
  it("setWorkflowEnabled parses the workflow enable response with Zod", () => {
    // Extract the setWorkflowEnabled function body for a focused check
    const setWorkflowEnabledMatch = workflowsSource.match(
      /setWorkflowEnabled[\s\S]*?(?=\n {2}\w|\n\};)/,
    );
    expect(setWorkflowEnabledMatch).not.toBeNull();
    const fnBody = setWorkflowEnabledMatch![0];
    expect(fnBody).toMatch(/\.parse\(/);
  });

  it("cancelRun parses the cancel response with Zod", () => {
    const cancelRunMatch = runsSource.match(/cancelRun[\s\S]*?(?=\n {2}\w|\n\};)/);
    expect(cancelRunMatch).not.toBeNull();
    const fnBody = cancelRunMatch![0];
    expect(fnBody).toMatch(/\.parse\(/);
  });

  it("cancelRun exposes a typed response instead of Promise<unknown>", () => {
    // The cancelRun signature must not use Promise<unknown>
    expect(runsSource).not.toMatch(/cancelRun[^}]*Promise<unknown>/);
  });

  it("dashboard hooks delegate fetching to the API client layer", () => {
    expect(dashboardQuerySource).not.toMatch(/\bapi\.get\(/);
  });

  it("git file reads use the shared FileReadResponseSchema", () => {
    // Must import from shared
    expect(gitSource).toMatch(/FileReadResponseSchema/);
    expect(gitSource).toMatch(/@runsight\/shared\/zod/);
    // Must NOT define a local GitFileResponseSchema
    expect(gitSource).not.toMatch(/GitFileResponseSchema/);
  });
});
