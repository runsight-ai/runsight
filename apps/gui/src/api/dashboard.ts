import { api } from "./client";
import { DashboardKPIsResponse, DashboardKPIsResponseSchema } from "../types/generated/zod";

export const dashboardApi = {
  getKPIs: async (): Promise<DashboardKPIsResponse> => {
    const res = await api.get(`/dashboard`);
    return DashboardKPIsResponseSchema.parse(res);
  },
};
