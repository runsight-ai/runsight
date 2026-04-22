import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "../client";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RUN-901 ApiError workflow input validation details", () => {
  it("preserves workflow input validation codes and field details from backend error bodies", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 422,
      statusText: "Unprocessable Entity",
      json: async () => ({
        error: "Workflow input validation failed",
        error_code: "WORKFLOW_INPUT_VALIDATION_ERROR",
        status_code: 422,
        details: {
          kind: "workflow_input_validation",
          workflow_id: "wf_901",
          fields: [
            {
              field: "query",
              code: "required",
              message: "Input 'query' is required.",
              input_path: ["inputs", "query"],
              expected_type: "string",
              actual_type: null,
            },
          ],
        },
      }),
    } as Response);

    const promise = api.post("/runs", {
      workflow_id: "wf_901",
      inputs: {},
    });

    await expect(promise).rejects.toBeInstanceOf(ApiError);
    await expect(promise).rejects.toMatchObject({
      name: "ApiError",
      status: 422,
      code: "WORKFLOW_INPUT_VALIDATION_ERROR",
      message: "Workflow input validation failed",
      details: {
        kind: "workflow_input_validation",
        workflow_id: "wf_901",
        fields: [
          {
            field: "query",
            code: "required",
            message: "Input 'query' is required.",
            input_path: ["inputs", "query"],
            expected_type: "string",
            actual_type: null,
          },
        ],
      },
    });
  });
});
