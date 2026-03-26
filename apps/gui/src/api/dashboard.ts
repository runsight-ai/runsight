import { api } from "./client";
import {
  DashboardKPIsResponse,
  DashboardKPIsResponseSchema,
  AttentionItemsResponse,
  AttentionItemsResponseSchema,
} from "../types/generated/zod";

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
