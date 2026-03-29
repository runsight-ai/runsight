import { api } from "./client";
import {
  StatusResponseSchema,
  CommitResponseSchema,
  DiffResponseSchema,
  CommitEntrySchema,
  type StatusResponse,
  type CommitResponse,
  type DiffResponse,
  type CommitEntry,
} from "../types/generated/zod";
import { z } from "zod";

/** Re-export api client type for consumers that need it. */
export type ApiClient = typeof api;

const GitLogResponseSchema = z.object({
  commits: z.array(CommitEntrySchema),
});

export const gitApi = {
  getStatus: async (): Promise<StatusResponse> => {
    const { api } = await import("./client");
    const res = await api.get("/git/status");
    return StatusResponseSchema.parse(res);
  },

  commit: async (message: string): Promise<CommitResponse> => {
    const { api } = await import("./client");
    const res = await api.post("/git/commit", { message });
    return CommitResponseSchema.parse(res);
  },

  getDiff: async (): Promise<DiffResponse> => {
    const { api } = await import("./client");
    const res = await api.get("/git/diff");
    return DiffResponseSchema.parse(res);
  },

  getLog: async (limit?: number): Promise<CommitEntry[]> => {
    const { api } = await import("./client");
    const qs = limit !== undefined ? `?limit=${limit}` : "";
    const res = await api.get(`/git/log${qs}`);
    const parsed = GitLogResponseSchema.parse(res);
    return parsed.commits;
  },
};
