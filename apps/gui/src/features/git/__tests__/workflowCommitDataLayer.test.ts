import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  apiPost: vi.fn(),
  invalidateQueries: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("../../../api/client", () => ({
  api: {
    post: mocks.apiPost,
    get: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
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
  mocks.apiPost.mockReset();
  mocks.invalidateQueries.mockReset();
  mocks.toastSuccess.mockReset();
  mocks.toastError.mockReset();
});

describe("workflow commit data layer (RUN-424)", () => {
  it("posts workflow save payloads through the API client to /workflows/:id/commits", async () => {
    mocks.apiPost.mockResolvedValue({
      hash: "abc123def456",
      message: "Save workflow to main",
    });

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

    expect(mocks.apiPost).toHaveBeenCalledWith("/workflows/wf_1/commits", {
      yaml: "workflow:\n  name: Updated Flow\n",
      canvas_state: { nodes: [], edges: [] },
      message: "Save workflow to main",
    });
    expect(result).toEqual({
      hash: "abc123def456",
      message: "Save workflow to main",
    });
  });

  it("rejects a malformed workflow commit payload instead of fabricating success", async () => {
    mocks.apiPost.mockResolvedValue({
      message: "Save workflow to main",
    });

    const { gitApi } = await import("../../../api/git");

    await expect(
      (gitApi as {
        commitWorkflow: (
          workflowId: string,
          payload: { yaml: string; message: string; canvas_state?: Record<string, unknown> },
        ) => Promise<unknown>;
      }).commitWorkflow("wf_1", {
        yaml: "workflow:\n  name: Updated Flow\n",
        canvas_state: { nodes: [], edges: [] },
        message: "Save workflow to main",
      }),
    ).rejects.toThrow(/commit.*(contract|response)/i);
  });

  it("preserves backend failures distinctly from commit contract failures", async () => {
    mocks.apiPost.mockRejectedValue(new Error("Network down"));

    const { useCommitWorkflow } = await import("../../../queries/git");

    const mutation = (
      useCommitWorkflow as unknown as () => {
        mutationFn?: (variables: {
          workflowId: string;
          payload: { yaml: string; message: string; canvas_state?: Record<string, unknown> };
        }) => Promise<unknown>;
      }
    )();

    await expect(
      mutation.mutationFn?.({
        workflowId: "wf_1",
        payload: {
          yaml: "workflow:\n  name: Updated Flow\n",
          canvas_state: { nodes: [], edges: [] },
          message: "Save workflow to main",
        },
      }),
    ).rejects.toThrow("Network down");
  });

  it("invalidates workflow and git queries after a successful production workflow save", async () => {
    const { queryKeys } = await import("../../../queries/keys");
    const { useCommitWorkflow } = await import("../../../queries/git");

    expect(useCommitWorkflow).toBeTypeOf("function");

    const mutation = (
      useCommitWorkflow as unknown as () => {
        mutationFn?: (variables: {
          workflowId: string;
          payload: { yaml: string; message: string; canvas_state?: Record<string, unknown> };
        }) => Promise<unknown>;
        onSuccess?: (
          data: { hash: string; message: string },
          variables: { workflowId: string },
        ) => void;
      }
    )();

    await mutation.mutationFn?.({
      workflowId: "wf_1",
      payload: {
        yaml: "workflow:\n  name: Updated Flow\n",
        canvas_state: { nodes: [], edges: [] },
        message: "Save workflow to main",
      },
    });

    expect(mocks.apiPost).toHaveBeenCalledWith("/workflows/wf_1/commits", {
      yaml: "workflow:\n  name: Updated Flow\n",
      canvas_state: { nodes: [], edges: [] },
      message: "Save workflow to main",
    });

    mutation.onSuccess?.(
      { hash: "abc123def456", message: "Save workflow to main" },
      { workflowId: "wf_1" },
    );

    expect(mocks.invalidateQueries).toHaveBeenCalledWith({
      queryKey: queryKeys.workflows.detail("wf_1"),
    });
    expect(mocks.invalidateQueries).toHaveBeenCalledWith({
      queryKey: queryKeys.git.status,
    });
    expect(mocks.toastSuccess).toHaveBeenCalledWith(
      expect.stringContaining("abc123def456"),
      expect.objectContaining({
        description: expect.stringContaining("Save workflow to main"),
      }),
    );
  });
});
