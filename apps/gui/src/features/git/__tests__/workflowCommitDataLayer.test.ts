import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  invalidateQueries: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(),
  useQueryClient: () => ({ invalidateQueries: mocks.invalidateQueries }),
  useMutation: (options: Record<string, unknown>) => options,
}));

vi.mock("sonner", () => ({
  toast: {
    success: mocks.toastSuccess,
    error: mocks.toastError,
  },
}));

beforeEach(() => {
  vi.resetModules();
  vi.unstubAllGlobals();
  mocks.invalidateQueries.mockReset();
  mocks.toastSuccess.mockReset();
  mocks.toastError.mockReset();
});

describe("workflow commit data layer (RUN-424)", () => {
  it("posts the in-memory workflow payload to /workflows/:id/commits", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ hash: "abc123def456", message: "Save workflow to main" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const { gitApi } = await import("../../../api/git");

    expect((gitApi as Record<string, unknown>).commitWorkflow).toBeTypeOf("function");

    const result = await (gitApi as {
      commitWorkflow: (
        workflowId: string,
        payload: { yaml: string; message: string; canvas_state?: Record<string, unknown> },
      ) => Promise<unknown>;
    }).commitWorkflow("wf_1", {
      yaml: "workflow:\n  name: Updated Flow\n",
      canvas_state: { nodes: [], edges: [] },
      message: "Save workflow to main",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/workflows/wf_1/commits",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          yaml: "workflow:\n  name: Updated Flow\n",
          canvas_state: { nodes: [], edges: [] },
          message: "Save workflow to main",
        }),
      }),
    );
    expect(result).toEqual({
      hash: "abc123def456",
      message: "Save workflow to main",
    });
  });

  it("surfaces commit metadata in the explicit workflow save toast", async () => {
    const { useCommitWorkflow } = await import("../../../queries/git");

    expect(useCommitWorkflow).toBeTypeOf("function");

    const mutation = (
      useCommitWorkflow as unknown as () => {
        onSuccess?: (
          data: { hash: string; message: string },
          variables: { workflowId: string },
        ) => void;
      }
    )();

    mutation.onSuccess?.(
      { hash: "abc123def456", message: "Save workflow to main" },
      { workflowId: "wf_1" },
    );

    expect(mocks.invalidateQueries).toHaveBeenCalled();
    expect(mocks.toastSuccess).toHaveBeenCalledWith(
      expect.stringContaining("abc123def456"),
      expect.objectContaining({
        description: expect.stringContaining("Save workflow to main"),
      }),
    );
  });
});
