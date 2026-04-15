/**
 * RED-TEAM tests for RUN-154: Git frontend data layer.
 *
 * Tests cover three layers:
 * 1. Zod schemas  — valid/invalid parsing, field presence
 * 2. API client   — correct endpoints, Zod parsing
 * 3. React Query hooks — query keys, polling, cache invalidation
 *
 * All tests must FAIL until Green-team implements:
 * - packages/shared/src/zod.ts (Git schemas)
 * - apps/gui/src/api/git.ts
 * - apps/gui/src/queries/git.ts
 */

import { describe, it, expect, vi } from "vitest";
import { readFileSync, existsSync } from "fs";
import { resolve } from "path";

// ---------------------------------------------------------------------------
// Helpers: path constants
// ---------------------------------------------------------------------------

const SCHEMAS_PATH = resolve(
  __dirname,
  "../../../../../../packages/shared/src/zod.ts",
);
const API_CLIENT_PATH = resolve(__dirname, "../../../api/git.ts");
const HOOKS_PATH = resolve(__dirname, "../../../queries/git.ts");
const KEYS_PATH = resolve(__dirname, "../../../queries/keys.ts");
// ===========================================================================
// SECTION 1: Zod Schemas
// ===========================================================================

describe("Git Zod schemas (RUN-154)", () => {
  // Guard: file must exist before any schema test runs
  it("schema file exists at packages/shared/src/zod.ts", () => {
    expect(existsSync(SCHEMAS_PATH)).toBe(true);
  });

  // We dynamically import so the rest of the suite still reports useful failures
  // even when the file is missing (the guard test above catches that).

  describe("UncommittedFileSchema", () => {
    it("parses a valid file status object", async () => {
      const { UncommittedFileSchema } = await import("@runsight/shared/zod");
      const result = UncommittedFileSchema.safeParse({
        path: "src/app.ts",
        status: "modified",
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.path).toBe("src/app.ts");
        expect(result.data.status).toBe("modified");
      }
    });

    it("rejects when path is missing", async () => {
      const { UncommittedFileSchema } = await import("@runsight/shared/zod");
      const result = UncommittedFileSchema.safeParse({ status: "modified" });
      expect(result.success).toBe(false);
    });

    it("rejects when status is missing", async () => {
      const { UncommittedFileSchema } = await import("@runsight/shared/zod");
      const result = UncommittedFileSchema.safeParse({ path: "foo.ts" });
      expect(result.success).toBe(false);
    });

    it("rejects non-string path", async () => {
      const { UncommittedFileSchema } = await import("@runsight/shared/zod");
      const result = UncommittedFileSchema.safeParse({ path: 123, status: "modified" });
      expect(result.success).toBe(false);
    });

    it("rejects non-string status", async () => {
      const { UncommittedFileSchema } = await import("@runsight/shared/zod");
      const result = UncommittedFileSchema.safeParse({ path: "foo.ts", status: true });
      expect(result.success).toBe(false);
    });
  });

  describe("StatusResponseSchema", () => {
    it("parses a valid status response", async () => {
      const { StatusResponseSchema } = await import("@runsight/shared/zod");
      const data = {
        branch: "main",
        uncommitted_files: [
          { path: "src/app.ts", status: "modified" },
          { path: "README.md", status: "untracked" },
        ],
        is_clean: false,
      };
      const result = StatusResponseSchema.safeParse(data);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.branch).toBe("main");
        expect(result.data.uncommitted_files).toHaveLength(2);
        expect(result.data.is_clean).toBe(false);
      }
    });

    it("parses a clean repo response", async () => {
      const { StatusResponseSchema } = await import("@runsight/shared/zod");
      const result = StatusResponseSchema.safeParse({
        branch: "feat/foo",
        uncommitted_files: [],
        is_clean: true,
      });
      expect(result.success).toBe(true);
    });

    it("rejects when branch is missing", async () => {
      const { StatusResponseSchema } = await import("@runsight/shared/zod");
      const result = StatusResponseSchema.safeParse({
        uncommitted_files: [],
        is_clean: true,
      });
      expect(result.success).toBe(false);
    });

    it("rejects when uncommitted_files is not an array", async () => {
      const { StatusResponseSchema } = await import("@runsight/shared/zod");
      const result = StatusResponseSchema.safeParse({
        branch: "main",
        uncommitted_files: "not-an-array",
        is_clean: true,
      });
      expect(result.success).toBe(false);
    });

    it("rejects when is_clean is missing", async () => {
      const { StatusResponseSchema } = await import("@runsight/shared/zod");
      const result = StatusResponseSchema.safeParse({
        branch: "main",
        uncommitted_files: [],
      });
      expect(result.success).toBe(false);
    });

    it("has exactly the fields: branch, uncommitted_files, is_clean", async () => {
      const { StatusResponseSchema } = await import("@runsight/shared/zod");
      const keys = Object.keys(StatusResponseSchema.shape).sort();
      expect(keys).toEqual(["branch", "is_clean", "uncommitted_files"]);
    });
  });

  describe("CommitResponseSchema", () => {
    it("parses a valid commit response", async () => {
      const { CommitResponseSchema } = await import("@runsight/shared/zod");
      const result = CommitResponseSchema.safeParse({
        hash: "abc123def456",
        message: "feat: add git integration",
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.hash).toBe("abc123def456");
        expect(result.data.message).toBe("feat: add git integration");
      }
    });

    it("rejects when hash is missing", async () => {
      const { CommitResponseSchema } = await import("@runsight/shared/zod");
      const result = CommitResponseSchema.safeParse({ message: "hi" });
      expect(result.success).toBe(false);
    });

    it("rejects when message is missing", async () => {
      const { CommitResponseSchema } = await import("@runsight/shared/zod");
      const result = CommitResponseSchema.safeParse({ hash: "abc123" });
      expect(result.success).toBe(false);
    });

    it("has exactly the fields: hash, message", async () => {
      const { CommitResponseSchema } = await import("@runsight/shared/zod");
      const keys = Object.keys(CommitResponseSchema.shape).sort();
      expect(keys).toEqual(["hash", "message"]);
    });
  });

  describe("CommitEntrySchema", () => {
    it("parses a valid log entry", async () => {
      const { CommitEntrySchema } = await import("@runsight/shared/zod");
      const result = CommitEntrySchema.safeParse({
        hash: "abc123",
        message: "initial commit",
        date: "2026-03-18 10:00:00 -0700",
        author: "Jane Doe",
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.hash).toBe("abc123");
        expect(result.data.author).toBe("Jane Doe");
      }
    });

    it("rejects when any required field is missing", async () => {
      const { CommitEntrySchema } = await import("@runsight/shared/zod");
      // Missing author
      const result = CommitEntrySchema.safeParse({
        hash: "abc",
        message: "msg",
        date: "2026-01-01",
      });
      expect(result.success).toBe(false);
    });

    it("has exactly the fields: hash, message, date, author", async () => {
      const { CommitEntrySchema } = await import("@runsight/shared/zod");
      const keys = Object.keys(CommitEntrySchema.shape).sort();
      expect(keys).toEqual(["author", "date", "hash", "message"]);
    });
  });

  describe("DiffResponseSchema", () => {
    it("parses a valid diff response", async () => {
      const { DiffResponseSchema } = await import("@runsight/shared/zod");
      const result = DiffResponseSchema.safeParse({
        diff: "--- a/foo.ts\n+++ b/foo.ts\n@@ -1 +1 @@\n-old\n+new",
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.diff).toContain("foo.ts");
      }
    });

    it("parses an empty diff string", async () => {
      const { DiffResponseSchema } = await import("@runsight/shared/zod");
      const result = DiffResponseSchema.safeParse({ diff: "" });
      expect(result.success).toBe(true);
    });

    it("rejects when diff is missing", async () => {
      const { DiffResponseSchema } = await import("@runsight/shared/zod");
      const result = DiffResponseSchema.safeParse({});
      expect(result.success).toBe(false);
    });

    it("has exactly the field: diff", async () => {
      const { DiffResponseSchema } = await import("@runsight/shared/zod");
      const keys = Object.keys(DiffResponseSchema.shape).sort();
      expect(keys).toEqual(["diff"]);
    });
  });
});

// ===========================================================================
// SECTION 2: API Client
// ===========================================================================

describe("Git API client (RUN-154)", () => {
  it("api client file exists at api/git.ts", () => {
    expect(existsSync(API_CLIENT_PATH)).toBe(true);
  });

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

  describe("API client source-level checks", () => {
    it("imports from api/client", () => {
      const source = readFileSync(API_CLIENT_PATH, "utf-8");
      expect(source).toMatch(/import\s*\{[^}]*api[^}]*\}\s*from\s*["']\.\/client["']/);
    });

    it("imports Zod schemas from @runsight/shared/zod", () => {
      const source = readFileSync(API_CLIENT_PATH, "utf-8");
      expect(source).toMatch(/from\s*["']@runsight\/shared\/zod["']/);
    });

    it("calls .parse() on responses for type safety", () => {
      const source = readFileSync(API_CLIENT_PATH, "utf-8");
      // Each endpoint should parse with the corresponding schema
      expect(source).toMatch(/StatusResponseSchema\.parse/);
      expect(source).toMatch(/CommitResponseSchema\.parse/);
      expect(source).toMatch(/DiffResponseSchema\.parse/);
    });

    it("exports gitApi object with all four methods", () => {
      const source = readFileSync(API_CLIENT_PATH, "utf-8");
      expect(source).toMatch(/export\s+const\s+gitApi/);
      expect(source).toContain("getStatus");
      expect(source).toContain("commit");
      expect(source).toContain("getDiff");
      expect(source).toContain("getLog");
    });

    it("getStatus calls GET /git/status", () => {
      const source = readFileSync(API_CLIENT_PATH, "utf-8");
      expect(source).toMatch(/api\.get.*\/git\/status/);
    });

    it("commit calls POST /git/commit", () => {
      const source = readFileSync(API_CLIENT_PATH, "utf-8");
      expect(source).toMatch(/api\.post.*\/git\/commit/);
    });

    it("getDiff calls GET /git/diff", () => {
      const source = readFileSync(API_CLIENT_PATH, "utf-8");
      expect(source).toMatch(/api\.get.*\/git\/diff/);
    });

    it("getLog calls GET /git/log", () => {
      const source = readFileSync(API_CLIENT_PATH, "utf-8");
      expect(source).toMatch(/api\.get.*\/git\/log/);
    });
  });
});

// ===========================================================================
// SECTION 3: React Query Hooks
// ===========================================================================

describe("Git React Query hooks (RUN-154)", () => {
  it("hooks file exists at queries/git.ts", () => {
    expect(existsSync(HOOKS_PATH)).toBe(true);
  });

  describe("Source-level contract checks", () => {
    it("imports from @tanstack/react-query", () => {
      const source = readFileSync(HOOKS_PATH, "utf-8");
      expect(source).toMatch(/from\s*["']@tanstack\/react-query["']/);
    });

    it("imports gitApi from api/git", () => {
      const source = readFileSync(HOOKS_PATH, "utf-8");
      expect(source).toMatch(/from\s*["']\.\.\/api\/git["']/);
    });

    it("imports queryKeys from ./keys", () => {
      const source = readFileSync(HOOKS_PATH, "utf-8");
      expect(source).toMatch(/from\s*["']\.\/keys["']/);
    });

    it("exports useGitStatus hook", () => {
      const source = readFileSync(HOOKS_PATH, "utf-8");
      expect(source).toMatch(/export\s+function\s+useGitStatus/);
    });

    it("exports useGitLog hook", () => {
      const source = readFileSync(HOOKS_PATH, "utf-8");
      expect(source).toMatch(/export\s+function\s+useGitLog/);
    });

    it("exports useGitDiff hook", () => {
      const source = readFileSync(HOOKS_PATH, "utf-8");
      expect(source).toMatch(/export\s+function\s+useGitDiff/);
    });

    it("exports useCommit mutation hook", () => {
      const source = readFileSync(HOOKS_PATH, "utf-8");
      expect(source).toMatch(/export\s+function\s+useCommit/);
    });
  });

  describe("useGitStatus polling", () => {
    it("uses POLL_INTERVALS.gitStatus (5000ms) as refetchInterval", () => {
      const source = readFileSync(HOOKS_PATH, "utf-8");
      // Should reference POLL_INTERVALS.gitStatus or the 5_000 / 5000 value
      expect(source).toMatch(/POLL_INTERVALS\.gitStatus|refetchInterval.*5.?000/);
    });

    it("imports POLL_INTERVALS from utils/constants", () => {
      const source = readFileSync(HOOKS_PATH, "utf-8");
      expect(source).toMatch(/import.*POLL_INTERVALS.*from\s*["']\.\.\/utils\/constants["']/);
    });

    it("supports an enabled option to disable polling", () => {
      const source = readFileSync(HOOKS_PATH, "utf-8");
      // The useGitStatus function should accept options with enabled
      expect(source).toMatch(/enabled/);
    });

    it("uses queryKeys.git.status as the query key", () => {
      const source = readFileSync(HOOKS_PATH, "utf-8");
      expect(source).toMatch(/queryKeys\.git\.status/);
    });
  });

  describe("useGitLog", () => {
    it("includes limit in the query key", () => {
      const source = readFileSync(HOOKS_PATH, "utf-8");
      // The query key should include the limit parameter for proper caching
      expect(source).toMatch(/queryKey.*git.*log.*limit|queryKey.*\[.*queryKeys\.git\.log.*limit/);
    });

    it("uses queryKeys.git.log as the base query key", () => {
      const source = readFileSync(HOOKS_PATH, "utf-8");
      expect(source).toMatch(/queryKeys\.git\.log/);
    });
  });

  describe("useGitDiff", () => {
    it("uses a git diff query key", () => {
      const source = readFileSync(HOOKS_PATH, "utf-8");
      expect(source).toMatch(/queryKeys\.git\.diff|queryKey.*["']git["'].*["']diff["']/);
    });
  });

  describe("useCommit mutation", () => {
    it("uses useMutation", () => {
      const source = readFileSync(HOOKS_PATH, "utf-8");
      expect(source).toMatch(/useMutation/);
    });

    it("calls gitApi.commit as the mutationFn", () => {
      const source = readFileSync(HOOKS_PATH, "utf-8");
      expect(source).toMatch(/gitApi\.commit|mutationFn.*commit/);
    });

    it("invalidates git status cache on success", () => {
      const source = readFileSync(HOOKS_PATH, "utf-8");
      expect(source).toMatch(/invalidateQueries.*git.*status|queryKeys\.git\.status/);
    });

    it("invalidates git log cache on success", () => {
      const source = readFileSync(HOOKS_PATH, "utf-8");
      expect(source).toMatch(/invalidateQueries.*git.*log|queryKeys\.git\.log/);
    });

    it("uses useQueryClient for cache invalidation", () => {
      const source = readFileSync(HOOKS_PATH, "utf-8");
      expect(source).toMatch(/useQueryClient/);
    });
  });
});

// ===========================================================================
// SECTION 4: Query Keys integration
// ===========================================================================

describe("Query keys for git (RUN-154)", () => {
  it("queryKeys.git.diff is defined in keys.ts", () => {
    const source = readFileSync(KEYS_PATH, "utf-8");
    expect(source).toMatch(/diff\s*:/);
    // Verify it is inside the git block
    expect(source).toMatch(/git\s*:\s*\{[^}]*diff/);
  });
});
