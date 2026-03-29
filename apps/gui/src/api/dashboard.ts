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
  getAttentionItems: async (): Promise<AttentionItemsResponse> => {
    const res = await api.get(`/dashboard/attention`);
    return AttentionItemsResponseSchema.parse(res);
  },
};
