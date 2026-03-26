import { api } from "./client";
import { DashboardResponse, DashboardResponseSchema } from "../types/generated/zod";

export const dashboardApi = {
  getOverview: async (): Promise<DashboardResponse> => {
    const res = await api.get(`/dashboard`);
    return DashboardResponseSchema.parse(res);
  },
};
