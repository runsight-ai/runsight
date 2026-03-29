import {
  CommitEntrySchema,
  CommitResponseSchema,
  DiffResponseSchema,
  StatusResponseSchema,
} from "@runsight/shared/zod";
import type {
  CommitEntry,
  CommitResponse,
  DiffResponse,
  StatusResponse,
} from "@runsight/shared/zod";
import { z } from "zod";

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
