import { api } from "./client";
import {
  WorkflowResponse,
  WorkflowResponseSchema,
  WorkflowListResponse,
  WorkflowListResponseSchema,
  WorkflowCreate,
  WorkflowUpdate,
} from "../types/generated/zod";

export const workflowsApi = {
  listWorkflows: async (): Promise<WorkflowListResponse> => {
    const res = await api.get(`/workflows`);
    return WorkflowListResponseSchema.parse(res);
  },

  getWorkflow: async (id: string): Promise<WorkflowResponse> => {
    const res = await api.get(`/workflows/${id}`);
    return WorkflowResponseSchema.parse(res);
  },

  createWorkflow: async (data: WorkflowCreate): Promise<WorkflowResponse> => {
    const res = await api.post(`/workflows`, data);
    return WorkflowResponseSchema.parse(res);
  },

  updateWorkflow: async (id: string, data: WorkflowUpdate): Promise<WorkflowResponse> => {
    const res = await api.put(`/workflows/${id}`, data);
    return WorkflowResponseSchema.parse(res);
  },

  deleteWorkflow: async (id: string): Promise<{ id: string; deleted: boolean }> => {
    const res = await api.delete<{ id: string; deleted: boolean }>(`/workflows/${id}`);
    return res;
  },
};
