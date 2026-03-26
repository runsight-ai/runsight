import { api } from "./client";
import {
  GitStatusResponseSchema,
  GitCommitResponseSchema,
  GitDiffResponseSchema,
  GitLogEntrySchema,
  type GitStatusResponse,
  type GitCommitResponse,
  type GitDiffResponse,
  type GitLogEntry,
} from "../types/generated/zod";
import { z } from "zod";

/** Re-export api client type for consumers that need it. */
export type ApiClient = typeof api;

const GitLogResponseSchema = z.object({
  commits: z.array(GitLogEntrySchema),
});

export const gitApi = {
  getStatus: async (): Promise<GitStatusResponse> => {
    const { api } = await import("./client");
    const res = await api.get("/git/status");
    return GitStatusResponseSchema.parse(res);
  },

  commit: async (message: string): Promise<GitCommitResponse> => {
    const { api } = await import("./client");
    const res = await api.post("/git/commit", { message });
    return GitCommitResponseSchema.parse(res);
  },

  getDiff: async (): Promise<GitDiffResponse> => {
    const { api } = await import("./client");
    const res = await api.get("/git/diff");
    return GitDiffResponseSchema.parse(res);
  },

  getLog: async (limit?: number): Promise<GitLogEntry[]> => {
    const { api } = await import("./client");
    const qs = limit !== undefined ? `?limit=${limit}` : "";
    const res = await api.get(`/git/log${qs}`);
    const parsed = GitLogResponseSchema.parse(res);
    return parsed.commits;
  },
};
