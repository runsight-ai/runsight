/**
 * Git frontend data layer coverage.
 *
 * Tests cover GUI-owned layers:
 * 1. API client — correct endpoints and response parsing calls
 * 2. React Query hooks — query keys, polling, cache invalidation
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

type QueryConfig = {
  queryKey: readonly unknown[];
  queryFn: () => Promise<unknown>;
  refetchInterval?: number;
  enabled?: boolean;
};

type MutationConfig = {
  mutationFn: (variables: unknown) => Promise<unknown>;
  onSuccess?: (data?: unknown, variables?: unknown) => void;
  onError?: (error: Error) => void;
};

async function loadGitHooksWithMocks() {
  const queryClient = { invalidateQueries: vi.fn() };
  const useQuery = vi.fn((config: QueryConfig) => config);
  const useMutation = vi.fn((config: MutationConfig) => config);
  const gitApi = {
    getStatus: vi.fn().mockResolvedValue({ is_clean: true, uncommitted_files: [] }),
    getLog: vi.fn().mockResolvedValue([]),
    getDiff: vi.fn().mockResolvedValue({ diff: "diff --git a/file b/file" }),
    commit: vi.fn().mockResolvedValue({ hash: "abc123", message: "save" }),
    commitWorkflow: vi.fn().mockResolvedValue({ hash: "def456", message: "save workflow" }),
  };
  const toast = {
    success: vi.fn(),
    error: vi.fn(),
  };

  vi.resetModules();
  vi.doMock("@tanstack/react-query", () => ({
    useQuery,
    useMutation,
    useQueryClient: () => queryClient,
  }));
  vi.doMock("sonner", () => ({ toast }));
  vi.doMock("../../../api/git", () => ({ gitApi }));

  const hooks = await import("../../../queries/git");

  return { gitApi, hooks, queryClient, toast, useMutation, useQuery };
}

beforeEach(() => {
  vi.resetModules();
  vi.unmock("@tanstack/react-query");
  vi.unmock("sonner");
  vi.unmock("../../../api/git");
  vi.unmock("../../../api/client");
});

// ===========================================================================
// SECTION 1: API Client
// ===========================================================================

describe("Git API client", () => {
  describe("gitApi.getStatus()", () => {
    it("calls GET /git/status and parses with GitStatusResponseSchema", async () => {
      // Mock the underlying fetch/api client
      const mockResponse = {
        branch: "main",
        uncommitted_files: [{ path: "file.ts", status: "modified" }],
        is_clean: false,
      };

      // Mock the api.get to return our fixture
      vi.doMock("../../../api/client", () => ({
        api: {
          get: vi.fn().mockResolvedValue(mockResponse),
          post: vi.fn(),
          put: vi.fn(),
          delete: vi.fn(),
        },
      }));

      // Clear module cache to pick up mock
      const { gitApi } = await import("../../../api/git");
      const result = await gitApi.getStatus();

      expect(result.branch).toBe("main");
      expect(result.uncommitted_files).toHaveLength(1);
      expect(result.is_clean).toBe(false);

      vi.doUnmock("../../../api/client");
    });

    it("throws on invalid response data from /git/status", async () => {
      vi.resetModules();
      vi.doMock("../../../api/client", () => ({
        api: {
          get: vi.fn().mockResolvedValue({ bad: "data" }),
          post: vi.fn(),
          put: vi.fn(),
          delete: vi.fn(),
        },
      }));

      const { gitApi } = await import("../../../api/git");
      await expect(gitApi.getStatus()).rejects.toThrow();

      vi.doUnmock("../../../api/client");
    });
  });

  describe("gitApi.commit(message)", () => {
    it("calls POST /git/commit with message and parses GitCommitResponseSchema", async () => {
      const mockResponse = { hash: "abc123", message: "feat: test" };

      vi.resetModules();
      vi.doMock("../../../api/client", () => ({
        api: {
          get: vi.fn(),
          post: vi.fn().mockResolvedValue(mockResponse),
          put: vi.fn(),
          delete: vi.fn(),
        },
      }));

      const { gitApi } = await import("../../../api/git");
      const result = await gitApi.commit("feat: test");

      expect(result.hash).toBe("abc123");
      expect(result.message).toBe("feat: test");

      vi.doUnmock("../../../api/client");
    });
  });

  describe("gitApi.getDiff()", () => {
    it("calls GET /git/diff and parses GitDiffResponseSchema", async () => {
      const mockResponse = { diff: "--- a/foo\n+++ b/foo" };

      vi.resetModules();
      vi.doMock("../../../api/client", () => ({
        api: {
          get: vi.fn().mockResolvedValue(mockResponse),
          post: vi.fn(),
          put: vi.fn(),
          delete: vi.fn(),
        },
      }));

      const { gitApi } = await import("../../../api/git");
      const result = await gitApi.getDiff();

      expect(result.diff).toContain("foo");

      vi.doUnmock("../../../api/client");
    });
  });

  describe("gitApi.getLog(limit?)", () => {
    it("calls GET /git/log and returns parsed GitLogEntry array", async () => {
      const mockResponse = {
        commits: [
          { hash: "abc", message: "first", date: "2026-03-18", author: "Jane" },
        ],
      };

      vi.resetModules();
      vi.doMock("../../../api/client", () => ({
        api: {
          get: vi.fn().mockResolvedValue(mockResponse),
          post: vi.fn(),
          put: vi.fn(),
          delete: vi.fn(),
        },
      }));

      const { gitApi } = await import("../../../api/git");
      const result = await gitApi.getLog();

      expect(Array.isArray(result)).toBe(true);
      expect(result).toHaveLength(1);
      expect(result[0].hash).toBe("abc");

      vi.doUnmock("../../../api/client");
    });

    it("passes limit as query parameter when provided", async () => {
      const getMock = vi.fn().mockResolvedValue({ commits: [] });

      vi.resetModules();
      vi.doMock("../../../api/client", () => ({
        api: {
          get: getMock,
          post: vi.fn(),
          put: vi.fn(),
          delete: vi.fn(),
        },
      }));

      const { gitApi } = await import("../../../api/git");
      await gitApi.getLog(10);

      // The GET call should include limit in URL
      expect(getMock).toHaveBeenCalledWith(
        expect.stringContaining("limit=10")
      );

      vi.doUnmock("../../../api/client");
    });
  });
});

// ===========================================================================
// SECTION 2: React Query Hooks
// ===========================================================================

describe("Git React Query hooks", () => {
  describe("useGitStatus polling", () => {
    it("registers the git status query with polling and enabled option", async () => {
      const { gitApi, hooks, useQuery } = await loadGitHooksWithMocks();

      hooks.useGitStatus({ enabled: false });

      const config = useQuery.mock.calls[0]?.[0] as QueryConfig;
      expect(config.queryKey).toEqual(["git", "status"]);
      expect(config.enabled).toBe(false);
      expect(config.refetchInterval).toBe(5000);

      await config.queryFn();

      expect(gitApi.getStatus).toHaveBeenCalledTimes(1);
    });
  });

  describe("useGitLog", () => {
    it("includes limit in the query key and passes it to the API", async () => {
      const { gitApi, hooks, useQuery } = await loadGitHooksWithMocks();

      hooks.useGitLog(10);

      const config = useQuery.mock.calls[0]?.[0] as QueryConfig;
      expect(config.queryKey).toEqual(["git", "log", 10]);

      await config.queryFn();

      expect(gitApi.getLog).toHaveBeenCalledWith(10);
    });
  });

  describe("useGitDiff", () => {
    it("uses the git diff query key and calls the diff API", async () => {
      const { gitApi, hooks, useQuery } = await loadGitHooksWithMocks();

      hooks.useGitDiff();

      const config = useQuery.mock.calls[0]?.[0] as QueryConfig;
      expect(config.queryKey).toEqual(["git", "diff"]);

      await config.queryFn();

      expect(gitApi.getDiff).toHaveBeenCalledTimes(1);
    });
  });

  describe("useCommit mutation", () => {
    it("commits through gitApi and invalidates git status and log on success", async () => {
      const { gitApi, hooks, queryClient, toast, useMutation } =
        await loadGitHooksWithMocks();

      hooks.useCommit();

      const config = useMutation.mock.calls[0]?.[0] as MutationConfig;
      await config.mutationFn("save changes");
      config.onSuccess?.();

      expect(gitApi.commit).toHaveBeenCalledWith("save changes");
      expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
        queryKey: ["git", "status"],
      });
      expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
        queryKey: ["git", "log"],
      });
      expect(toast.success).toHaveBeenCalledWith("Changes committed");
    });
  });

  describe("useCommitWorkflow mutation", () => {
    it("commits workflow drafts and invalidates workflow and git caches", async () => {
      const { gitApi, hooks, queryClient, toast, useMutation } =
        await loadGitHooksWithMocks();

      hooks.useCommitWorkflow();

      const config = useMutation.mock.calls[0]?.[0] as MutationConfig;
      const variables = {
        workflowId: "wf_git_save",
        payload: {
          yaml: "workflow:\n  name: Git Save\n",
          message: "save workflow",
        },
      };

      await config.mutationFn(variables);
      config.onSuccess?.({ hash: "def456", message: "save workflow" }, variables);

      expect(gitApi.commitWorkflow).toHaveBeenCalledWith(
        "wf_git_save",
        variables.payload,
      );
      expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
        queryKey: ["workflows", "wf_git_save"],
      });
      expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
        queryKey: ["git", "status"],
      });
      expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
        queryKey: ["git", "log"],
      });
      expect(toast.success).toHaveBeenCalledWith("Saved to main (def456)", {
        description: "save workflow",
      });
    });
  });
});
