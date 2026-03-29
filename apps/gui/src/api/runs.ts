import { api } from "./client";
import {
  RunCreate,
  RunResponseSchema,
  RunResponse,
  RunListResponseSchema,
  RunListResponse,
  RunNodeResponseSchema,
  RunNodeResponse,
  PaginatedLogsResponseSchema,
  PaginatedLogsResponse,
  CancelRunResponseSchema,
  CancelRunResponse,
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
      // Resolve aliases (e.g. "active" → ["running", "pending"])
      if (value in STATUS_ALIASES) {
        for (const v of STATUS_ALIASES[value]) {
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
  
  cancelRun: async (id: string): Promise<CancelRunResponse> => {
    const res = await api.post(`/runs/${id}/cancel`);
    return CancelRunResponseSchema.parse(res);
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
