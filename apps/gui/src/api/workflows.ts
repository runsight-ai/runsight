import { api } from "./client";
import {
  WorkflowListResponseSchema,
  WorkflowResponseSchema,
} from "@runsight/shared/zod";
import { parse, stringify } from "yaml";
import type {
  WorkflowCreate,
  WorkflowListResponse,
  WorkflowResponse,
  WorkflowUpdate,
} from "@runsight/shared/zod";
import {
  WorkflowRegressionsResponseSchema,
  type WorkflowRegressionsResponse,
} from "../types/schemas/regressions";

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

  setWorkflowEnabled: async (id: string, enabled: boolean): Promise<WorkflowResponse> => {
    const workflow = await workflowsApi.getWorkflow(id);
    const parsed = workflow.yaml ? parse(workflow.yaml) : {};
    const yamlDocument =
      parsed && typeof parsed === "object" && !Array.isArray(parsed)
        ? { ...(parsed as Record<string, unknown>), enabled }
        : { enabled };
    return workflowsApi.updateWorkflow(id, { yaml: stringify(yamlDocument) });
  },

  deleteWorkflow: async (id: string): Promise<{ id: string; deleted: boolean }> => {
    const res = await api.delete<{ id: string; deleted: boolean }>(`/workflows/${id}`);
    return res;
  },

  getWorkflowRegressions: async (workflowId: string): Promise<WorkflowRegressionsResponse> => {
    const res = await api.get(`/workflows/${workflowId}/regressions`);
    return WorkflowRegressionsResponseSchema.parse(res);
  },
};
