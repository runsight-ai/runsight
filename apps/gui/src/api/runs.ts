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
  ContextAuditListResponseSchema,
  type ContextAuditListResponse,
  type runsight_api__transport__schemas__runs__LogResponse as RunLogResponse,
} from "@runsight/shared/zod";
import { z } from "zod";

// ---------------------------------------------------------------------------
// Regressions
// ---------------------------------------------------------------------------

export const RunRegressionSchema = z.object({
  node_id: z.string(),
  node_name: z.string(),
  type: z.enum(["assertion_regression", "cost_spike", "quality_drop"]),
  delta: z.record(z.string(), z.unknown()),
});

export type RunRegression = z.infer<typeof RunRegressionSchema>;

export const RunRegressionsResponseSchema = z.object({
  count: z.number(),
  issues: z.array(RunRegressionSchema),
});

export type RunRegressionsResponse = z.infer<typeof RunRegressionsResponseSchema>;
export type RunContextAuditParams = {
  node_id?: string;
  cursor?: string;
  page_size?: number;
};

/** Map frontend shorthand status values to actual RunStatus enum values. */
const STATUS_ALIASES: Record<string, string[]> = {
  active: ["running", "pending"],
};

export type RunQueryParams = Record<string, string | string[]> | URLSearchParams;

function buildQueryString(params: RunQueryParams): string {
  if (params instanceof URLSearchParams) {
    return params.toString();
  }

  const sp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    const values = Array.isArray(value) ? value : [value];

    if (key === "status") {
      for (const statusValue of values) {
        const aliases = STATUS_ALIASES[statusValue];
        if (aliases) {
          for (const v of aliases) {
            sp.append(key, v);
          }
          continue;
        }

        const parts = statusValue.split(",");
        for (const part of parts) {
          sp.append(key, part);
        }
      }
    } else {
      for (const entry of values) {
        sp.append(key, entry);
      }
    }
  }
  return sp.toString();
}

export const runsApi = {
  listRuns: async (params?: RunQueryParams): Promise<RunListResponse> => {
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
  
  cancelRun: async (id: string): Promise<{ id: string; status: string }> => {
    const CancelRunResponseSchema = z.object({
      id: z.string(),
      status: z.string(),
    });
    const res = await api.post(`/runs/${id}/cancel`);
    return CancelRunResponseSchema.parse(res);
  },
  
  deleteRun: async (id: string): Promise<{ id: string; deleted: boolean }> => {
    const DeleteRunResponseSchema = z.object({
      id: z.string(),
      deleted: z.boolean(),
    });
    const res = await api.delete<{ id: string; deleted: boolean }>(`/runs/${id}`);
    return DeleteRunResponseSchema.parse(res);
  },

  getRunNodes: async (id: string): Promise<RunNodeResponse[]> => {
    const res = await api.get(`/runs/${id}/nodes`);
    const parsed = z.array(RunNodeResponseSchema).safeParse(res);
    if (!parsed.success) {
      throw new Error("Run node response contract invalid");
    }

    return parsed.data;
  },

  getRunLogs: async (id: string, params?: Record<string, string>): Promise<PaginatedLogsResponse> => {
    const qs = params ? `?${new URLSearchParams(params).toString()}` : "";
    const res = await api.get(`/runs/${id}/logs${qs}`);
    return PaginatedLogsResponseSchema.parse(res);
  },

  getRunContextAudit: async (
    id: string,
    params?: RunContextAuditParams,
  ): Promise<ContextAuditListResponse> => {
    const sp = new URLSearchParams();
    if (params?.node_id) {
      sp.set("node_id", params.node_id);
    }
    if (params?.cursor) {
      sp.set("cursor", params.cursor);
    }
    if (params?.page_size !== undefined) {
      sp.set("page_size", String(params.page_size));
    }
    const qs = sp.toString() ? `?${sp.toString()}` : "";
    const res = await api.get(`/runs/${id}/context-audit${qs}`);
    return ContextAuditListResponseSchema.parse(res);
  },

  getRunRegressions: async (id: string): Promise<RunRegressionsResponse> => {
    const res = await api.get(`/runs/${id}/regressions`);
    return RunRegressionsResponseSchema.parse(res);
  },

  getChildRuns: async (id: string): Promise<RunResponse[]> => {
    const res = await api.get(`/runs/${id}/children`);
    return z.array(RunResponseSchema).parse(res);
  },
};

export type { RunLogResponse };
