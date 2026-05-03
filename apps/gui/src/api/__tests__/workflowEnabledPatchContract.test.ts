import { beforeEach, describe, expect, it, vi } from "vitest";

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
  kind: "workflow",
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
    total_cost_usd: 0.1,
    regression_count: 0,
  },
};

describe("setWorkflowEnabled PATCH smoke", () => {
  it("patches the enabled flag without fetching or rewriting workflow YAML", async () => {
    testState.apiPatch
      .mockResolvedValueOnce(workflowResponsePayload)
      .mockResolvedValueOnce({ ...workflowResponsePayload, enabled: false });

    const { workflowsApi } = await import("../workflows");

    await expect(workflowsApi.setWorkflowEnabled("wf_toggle_test", true)).resolves.toMatchObject({
      id: "wf_toggle_test",
      enabled: true,
    });
    await expect(workflowsApi.setWorkflowEnabled("wf_toggle_test", false)).resolves.toMatchObject({
      id: "wf_toggle_test",
      enabled: false,
    });

    expect(testState.apiPatch).toHaveBeenNthCalledWith(
      1,
      "/workflows/wf_toggle_test/enabled",
      { enabled: true },
    );
    expect(testState.apiPatch).toHaveBeenNthCalledWith(
      2,
      "/workflows/wf_toggle_test/enabled",
      { enabled: false },
    );
    expect(testState.apiGet).not.toHaveBeenCalled();
    expect(testState.apiPut).not.toHaveBeenCalled();
  });
});
