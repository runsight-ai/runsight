import { api as staticApiClient } from "./client";
import {
  CommitEntrySchema,
  CommitResponseSchema,
  DiffResponseSchema,
  FileReadResponseSchema,
  StatusResponseSchema,
  WorkflowCommitResponseSchema,
} from "@runsight/shared/zod";
import type {
  CommitEntry,
  CommitResponse,
  DiffResponse,
  FileReadResponse,
  StatusResponse,
} from "@runsight/shared/zod";
import { z } from "zod";

const GitLogResponseSchema = z.object({
  commits: z.array(CommitEntrySchema),
});

const SimulationSnapshotResponseSchema = z.object({
  branch: z.string(),
  commit_sha: z.string(),
});

const WorkflowCommitPayloadSchema = z.object({
  name: z.string().optional(),
  description: z.string().optional(),
  yaml: z.string().optional(),
  canvas_state: z.record(z.string(), z.unknown()).optional(),
  message: z.string(),
});

const ensureStaticClientImport = staticApiClient;
void ensureStaticClientImport;

export const gitApi = {
  getGitFile: async (ref: string, path: string): Promise<FileReadResponse> => {
    const { api } = await import("./client");
    const res = await api.get(`/git/file?ref=${encodeURIComponent(ref)}&path=${encodeURIComponent(path)}`);
    return FileReadResponseSchema.parse(res);
  },

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

  createSimBranch: async (
    workflowId: string,
    yamlContent: string,
  ): Promise<{ branch: string; commit_sha: string }> => {
    const { api } = await import("./client");
    const res = await api.post(`/workflows/${workflowId}/simulations`, { yaml: yamlContent });
    return SimulationSnapshotResponseSchema.parse(res);
  },

  commitWorkflow: async (
    workflowId: string,
    payload: {
      name?: string;
      description?: string;
      yaml?: string;
      canvas_state?: Record<string, unknown>;
      message: string;
    },
  ): Promise<CommitResponse> => {
    const { api } = await import("./client");
    const request = WorkflowCommitPayloadSchema.parse(payload);
    const res = await api.post(`/workflows/${workflowId}/commits`, request);
    const parsed = WorkflowCommitResponseSchema.safeParse(res);
    if (parsed.success) {
      return parsed.data;
    }

    throw new Error("Commit response contract invalid");
  },
};
