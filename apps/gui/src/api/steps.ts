import { api } from "./client";
import {
  StepResponse,
  StepResponseSchema,
  StepListResponse,
  StepListResponseSchema,
  StepCreate,
  StepUpdate,
} from "../types/generated/zod";

export const stepsApi = {
  listSteps: async (params?: Record<string, string>): Promise<StepListResponse> => {
    const qs = params ? `?${new URLSearchParams(params).toString()}` : "";
    const res = await api.get(`/steps${qs}`);
    return StepListResponseSchema.parse(res);
  },

  getStep: async (id: string): Promise<StepResponse> => {
    const res = await api.get(`/steps/${id}`);
    return StepResponseSchema.parse(res);
  },

  createStep: async (data: StepCreate): Promise<StepResponse> => {
    const res = await api.post(`/steps`, data);
    return StepResponseSchema.parse(res);
  },

  updateStep: async (id: string, data: StepUpdate): Promise<StepResponse> => {
    const res = await api.put(`/steps/${id}`, data);
    return StepResponseSchema.parse(res);
  },

  deleteStep: async (id: string): Promise<{ id: string; deleted: boolean }> => {
    const res = await api.delete(`/steps/${id}`);
    return res as { id: string; deleted: boolean };
  },
};
