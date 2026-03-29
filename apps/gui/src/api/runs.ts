import { api } from "./client";
import {
  type RunCreate,
  RunResponseSchema,
  type RunResponse,
  RunListResponseSchema,
  type RunListResponse,
  RunNodeResponseSchema,
  type RunNodeResponse,
  PaginatedLogsResponseSchema,
  type PaginatedLogsResponse,
  type runsight_api__transport__schemas__runs__LogResponse as RunLogResponse,
} from "../types/generated/zod";

/** Map frontend shorthand status values to actual RunStatus enum values. */
const STATUS_ALIASES: Record<string, string[]> = {
  active: ["running", "pending"],
};

function buildQueryString(params: Record<string, string> | URLSearchParams): string {
  if (params instanceof URLSearchParams) {
    return params.toString();
  }

  const sp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (key === "status") {
      const aliases = STATUS_ALIASES[value];
      // Resolve aliases (e.g. "active" → ["running", "pending"])
      if (aliases) {
        for (const v of aliases) {
          sp.append(key, v);
        }
        continue;
      }
      // Split comma-separated values (e.g. "completed,failed" → two params)
      const parts = value.split(",");
      for (const part of parts) {
        sp.append(key, part);
      }
    } else {
      sp.append(key, value);
    }
  }
  return sp.toString();
}

export const runsApi = {
  listRuns: async (params?: Record<string, string> | URLSearchParams): Promise<RunListResponse> => {
    const qs = params ? `?${buildQueryString(params)}` : "";
    const res = await api.get(`/runs${qs}`);
    return RunListResponseSchema.parse(res);
  },
  
  getRun: async (id: string): Promise<RunResponse> => {
    const res = await api.get(`/runs/${id}`);
    return RunResponseSchema.parse(res);
  },
  
  createRun: async (data: RunCreate): Promise<RunResponse> => {
    const res = await api.post(`/runs`, data);
    return RunResponseSchema.parse(res);
  },
  
  cancelRun: async (id: string): Promise<unknown> => {
    return api.post(`/runs/${id}/cancel`);
  },
  
  deleteRun: async (id: string): Promise<{ id: string; deleted: boolean }> => {
    const res = await api.delete<{ id: string; deleted: boolean }>(`/runs/${id}`);
    return res;
  },

  getRunNodes: async (id: string): Promise<RunNodeResponse[]> => {
    // Note: Depends on backend implementation, but typically nodes are listed at /runs/:id/nodes
    const res = await api.get(`/runs/${id}/nodes`);
    // Assuming backend returns an array or an object with an array under `items`
    if (Array.isArray(res)) {
       return res.map(node => RunNodeResponseSchema.parse(node));
    }
    return []; 
  },

  getRunLogs: async (id: string, params?: Record<string, string>): Promise<PaginatedLogsResponse> => {
    const qs = params ? `?${new URLSearchParams(params).toString()}` : "";
    const res = await api.get(`/runs/${id}/logs${qs}`);
    return PaginatedLogsResponseSchema.parse(res);
  },
};

export type { RunLogResponse };
