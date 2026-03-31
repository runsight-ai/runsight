import { api } from "./client";
import {
  DashboardKPIsResponseSchema,
  AttentionItemsResponseSchema,
} from "@runsight/shared/zod";
import type {
  AttentionItemsResponse,
  DashboardKPIsResponse,
} from "@runsight/shared/zod";

export const dashboardApi = {
  getKPIs: async (): Promise<DashboardKPIsResponse> => {
    const res = await api.get(`/dashboard`);
    return DashboardKPIsResponseSchema.parse(res);
  },
  getAttentionItems: async (limit?: number): Promise<AttentionItemsResponse> => {
    const qs = limit != null ? `?limit=${limit}` : "";
    const res = await api.get(`/dashboard/attention${qs}`);
    return AttentionItemsResponseSchema.parse(res);
  },
};
