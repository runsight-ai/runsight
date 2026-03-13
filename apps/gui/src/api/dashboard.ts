import { api } from "./client";
import { DashboardResponse, DashboardResponseSchema } from "../types/schemas/dashboard";

export const dashboardApi = {
  getOverview: async (): Promise<DashboardResponse> => {
    const res = await api.get(`/dashboard`);
    return DashboardResponseSchema.parse(res);
  },
};
