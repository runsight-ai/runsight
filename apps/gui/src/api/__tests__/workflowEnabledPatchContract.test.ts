import { readFileSync } from "node:fs";
import { beforeEach, describe, expect, it, vi } from "vitest";

const workflowsSource = readFileSync(
  new URL("../workflows.ts", import.meta.url),
  "utf8",
);

const testState = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPatch: vi.fn(),
  apiPut: vi.fn(),
  apiPost: vi.fn(),
  apiDelete: vi.fn(),
}));

vi.mock("../client", () => ({
  api: {
    get: testState.apiGet,
    patch: testState.apiPatch,
    put: testState.apiPut,
    post: testState.apiPost,
    delete: testState.apiDelete,
  },
}));

beforeEach(() => {
  vi.resetModules();
  testState.apiGet.mockReset();
  testState.apiPatch.mockReset();
  testState.apiPut.mockReset();
  testState.apiPost.mockReset();
  testState.apiDelete.mockReset();
});

const workflowResponsePayload = {
  id: "wf_toggle_test",
  name: "Toggle Test",
  enabled: true,
  block_count: 2,
  modified_at: 1711900800,
  commit_sha: "abc1234",
  yaml: "name: Toggle Test\nenabled: true\n",
  health: {
    run_count: 5,
    eval_pass_pct: 80,
    eval_health: "success",
    total_cost_usd: 0.10,
    regression_count: 0,
  },
};

describe("RUN-566 setWorkflowEnabled uses PATCH endpoint", () => {
  it("calls PATCH /workflows/:id/enabled with { enabled } body", async () => {
    testState.apiPatch.mockResolvedValue(workflowResponsePayload);

    const { workflowsApi } = await import("../workflows");
    await workflowsApi.setWorkflowEnabled("wf_toggle_test", true);

    expect(testState.apiPatch).toHaveBeenCalledTimes(1);
    expect(testState.apiPatch).toHaveBeenCalledWith(
      "/workflows/wf_toggle_test/enabled",
      { enabled: true },
    );
  });

  it("calls PATCH with enabled=false when disabling", async () => {
    testState.apiPatch.mockResolvedValue({
      ...workflowResponsePayload,
      enabled: false,
    });

    const { workflowsApi } = await import("../workflows");
    await workflowsApi.setWorkflowEnabled("wf_toggle_test", false);

    expect(testState.apiPatch).toHaveBeenCalledTimes(1);
    expect(testState.apiPatch).toHaveBeenCalledWith(
      "/workflows/wf_toggle_test/enabled",
      { enabled: false },
    );
  });

  it("does not call GET or PUT (no YAML fetch-parse-rewrite cycle)", async () => {
    testState.apiPatch.mockResolvedValue(workflowResponsePayload);

    const { workflowsApi } = await import("../workflows");
    await workflowsApi.setWorkflowEnabled("wf_toggle_test", true);

    expect(testState.apiGet).not.toHaveBeenCalled();
    expect(testState.apiPut).not.toHaveBeenCalled();
  });

  it("does not import yaml parse/stringify in workflows.ts", () => {
    const yamlImportPattern = /import\s+.*\bfrom\s+["']yaml["']/;

    expect(
      yamlImportPattern.test(workflowsSource),
      [
        "Expected apps/gui/src/api/workflows.ts to not import from the 'yaml' package.",
        "The setWorkflowEnabled method should use PATCH, not YAML parse-rewrite.",
        "Remove: import { parse, stringify } from 'yaml'",
      ].join("\n"),
    ).toBe(false);
  });

  it("does not reference parse() or stringify() in setWorkflowEnabled", () => {
    const setWorkflowEnabledPattern =
      /setWorkflowEnabled\s*[:=]\s*async[\s\S]*?(?=\n\s{2}\w|\n\};)/;
    const match = workflowsSource.match(setWorkflowEnabledPattern);
    const methodBody = match?.[0] ?? "";

    expect(
      /\bparse\s*\(/.test(methodBody),
      "setWorkflowEnabled should not call parse() — YAML rewrite is the old approach",
    ).toBe(false);
    expect(
      /\bstringify\s*\(/.test(methodBody),
      "setWorkflowEnabled should not call stringify() — YAML rewrite is the old approach",
    ).toBe(false);
  });
});
