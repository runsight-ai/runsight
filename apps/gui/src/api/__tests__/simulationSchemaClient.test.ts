import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { WorkflowSimulationResponseSchema } from "@runsight/shared/zod";
import { gitApi } from "../git";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("simulation snapshot client contract", () => {
  it("createSimBranch returns the prepared input_schema alongside branch and commit_sha", async () => {
    const yamlContent = "workflow:\n  name: Audit Flow\n";
    const responsePayload = {
      branch: "sim/wf_simulation_schema/20260419/abc12",
      commit_sha: "1234567890abcdef1234567890abcdef12345678",
      input_schema: {
        query: {
          type: "string",
          required: true,
          default: null,
          description: "Search query",
          sensitive: false,
        },
      },
    };

    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => responsePayload,
    } as Response);

    const response = (await gitApi.createSimBranch("wf_simulation_schema", yamlContent)) as {
      branch: string;
      commit_sha: string;
      input_schema?: Record<string, unknown>;
    };

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/workflows/wf_simulation_schema/simulations",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ yaml: yamlContent }),
        headers: expect.objectContaining({
          "Content-Type": "application/json",
        }),
      }),
    );
    expect(WorkflowSimulationResponseSchema.safeParse(response).success).toBe(true);
    expect(response).toEqual(responsePayload);
  });

  it("createSimBranch rejects a simulation response with an unknown input type instead of guessing", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        branch: "sim/wf_simulation_schema/20260419/def34",
        commit_sha: "abcdef1234567890abcdef1234567890abcdef12",
        input_schema: {
          mystery: {
            type: "alien",
            required: true,
            default: null,
            description: "Unknown input",
            sensitive: false,
          },
        },
      }),
    } as Response);

    await expect(
      gitApi.createSimBranch("wf_simulation_schema", "workflow:\n  name: Broken Flow\n"),
    ).rejects.toThrow();
  });
});
