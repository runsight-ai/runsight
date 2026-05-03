import { describe, expect, it } from "vitest";
import {
  CommitEntrySchema,
  CommitResponseSchema,
  DiffResponseSchema,
  StatusResponseSchema,
  UncommittedFileSchema,
} from "../zod";

describe("Git shared response contracts", () => {
  describe("UncommittedFileSchema", () => {
    it("parses a valid file status object", () => {
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

    it("rejects missing or non-string fields", () => {
      expect(UncommittedFileSchema.safeParse({ status: "modified" }).success).toBe(false);
      expect(UncommittedFileSchema.safeParse({ path: "foo.ts" }).success).toBe(false);
      expect(
        UncommittedFileSchema.safeParse({ path: 123, status: "modified" }).success,
      ).toBe(false);
      expect(
        UncommittedFileSchema.safeParse({ path: "foo.ts", status: true }).success,
      ).toBe(false);
    });
  });

  describe("StatusResponseSchema", () => {
    it("parses dirty and clean status responses", () => {
      const dirty = StatusResponseSchema.safeParse({
        branch: "main",
        uncommitted_files: [
          { path: "src/app.ts", status: "modified" },
          { path: "README.md", status: "untracked" },
        ],
        is_clean: false,
      });
      const clean = StatusResponseSchema.safeParse({
        branch: "feat/foo",
        uncommitted_files: [],
        is_clean: true,
      });

      expect(dirty.success).toBe(true);
      expect(clean.success).toBe(true);
      if (dirty.success) {
        expect(dirty.data.branch).toBe("main");
        expect(dirty.data.uncommitted_files).toHaveLength(2);
        expect(dirty.data.is_clean).toBe(false);
      }
    });

    it("rejects malformed status responses", () => {
      expect(
        StatusResponseSchema.safeParse({
          uncommitted_files: [],
          is_clean: true,
        }).success,
      ).toBe(false);
      expect(
        StatusResponseSchema.safeParse({
          branch: "main",
          uncommitted_files: "not-an-array",
          is_clean: true,
        }).success,
      ).toBe(false);
      expect(
        StatusResponseSchema.safeParse({
          branch: "main",
          uncommitted_files: [],
        }).success,
      ).toBe(false);
    });

    it("keeps the status response field set stable", () => {
      expect(Object.keys(StatusResponseSchema.shape).sort()).toEqual([
        "branch",
        "is_clean",
        "uncommitted_files",
      ]);
    });
  });

  describe("CommitResponseSchema", () => {
    it("parses a valid commit response", () => {
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

    it("rejects missing commit response fields", () => {
      expect(CommitResponseSchema.safeParse({ message: "hi" }).success).toBe(false);
      expect(CommitResponseSchema.safeParse({ hash: "abc123" }).success).toBe(false);
    });

    it("keeps the commit response field set stable", () => {
      expect(Object.keys(CommitResponseSchema.shape).sort()).toEqual(["hash", "message"]);
    });
  });

  describe("CommitEntrySchema", () => {
    it("parses a valid log entry", () => {
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

    it("rejects missing log entry fields", () => {
      expect(
        CommitEntrySchema.safeParse({
          hash: "abc",
          message: "msg",
          date: "2026-01-01",
        }).success,
      ).toBe(false);
    });

    it("keeps the commit log entry field set stable", () => {
      expect(Object.keys(CommitEntrySchema.shape).sort()).toEqual([
        "author",
        "date",
        "hash",
        "message",
      ]);
    });
  });

  describe("DiffResponseSchema", () => {
    it("parses populated and empty diff responses", () => {
      const diff = DiffResponseSchema.safeParse({
        diff: "--- a/foo.ts\n+++ b/foo.ts\n@@ -1 +1 @@\n-old\n+new",
      });
      const empty = DiffResponseSchema.safeParse({ diff: "" });

      expect(diff.success).toBe(true);
      expect(empty.success).toBe(true);
      if (diff.success) {
        expect(diff.data.diff).toContain("foo.ts");
      }
    });

    it("rejects a missing diff field", () => {
      expect(DiffResponseSchema.safeParse({}).success).toBe(false);
    });

    it("keeps the diff response field set stable", () => {
      expect(Object.keys(DiffResponseSchema.shape).sort()).toEqual(["diff"]);
    });
  });
});
