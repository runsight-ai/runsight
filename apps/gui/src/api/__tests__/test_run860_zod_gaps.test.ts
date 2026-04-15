/**
 * Red tests for RUN-860: Fix frontend Zod validation gaps and dashboard query bypass.
 *
 * These tests verify that:
 * 1. setWorkflowEnabled uses Zod .parse() on the API response
 * 2. cancelRun uses Zod .parse() on the API response
 * 3. cancelRun does not have Promise<unknown> return type
 * 4. Dashboard hooks delegate to the API layer (no raw api.get calls)
 * 5. getGitFile uses the shared FileReadResponseSchema (no local schema)
 *
 * All tests FAIL before Green.
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

describe("RUN-860 Zod validation gaps", () => {
  it("test_setWorkflowEnabled_uses_zod_parse — workflows.ts setWorkflowEnabled must call .parse(", () => {
    // Extract the setWorkflowEnabled function body for a focused check
    const setWorkflowEnabledMatch = workflowsSource.match(
      /setWorkflowEnabled[\s\S]*?(?=\n  \w|\n\};)/,
    );
    expect(setWorkflowEnabledMatch).not.toBeNull();
    const fnBody = setWorkflowEnabledMatch![0];
    expect(fnBody).toMatch(/\.parse\(/);
  });

  it("test_cancelRun_uses_zod_parse — runs.ts cancelRun must call .parse(", () => {
    const cancelRunMatch = runsSource.match(/cancelRun[\s\S]*?(?=\n  \w|\n\};)/);
    expect(cancelRunMatch).not.toBeNull();
    const fnBody = cancelRunMatch![0];
    expect(fnBody).toMatch(/\.parse\(/);
  });

  it("test_cancelRun_not_promise_unknown — runs.ts cancelRun must not return Promise<unknown>", () => {
    // The cancelRun signature must not use Promise<unknown>
    expect(runsSource).not.toMatch(/cancelRun[^}]*Promise<unknown>/);
  });

  it("test_dashboard_hooks_use_api_layer — queries/dashboard.ts must not contain raw api.get( calls", () => {
    expect(dashboardQuerySource).not.toMatch(/\bapi\.get\(/);
  });

  it("test_git_uses_shared_schema — git.ts must import FileReadResponseSchema from shared (not define locally)", () => {
    // Must import from shared
    expect(gitSource).toMatch(/FileReadResponseSchema/);
    expect(gitSource).toMatch(/@runsight\/shared\/zod/);
    // Must NOT define a local GitFileResponseSchema
    expect(gitSource).not.toMatch(/GitFileResponseSchema/);
  });
});
