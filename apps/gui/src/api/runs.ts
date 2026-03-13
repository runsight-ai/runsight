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
} from "../types/schemas/runs";

export const runsApi = {
  listRuns: async (params?: Record<string, string>): Promise<RunListResponse> => {
    const qs = params ? `?${new URLSearchParams(params).toString()}` : "";
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
