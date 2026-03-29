import { api } from "./client";
import {
  TaskResponse,
  TaskResponseSchema,
  TaskListResponse,
  TaskListResponseSchema,
  TaskCreate,
  TaskUpdate,
} from "@runsight/shared/zod";

export const tasksApi = {
  listTasks: async (params?: Record<string, string>): Promise<TaskListResponse> => {
    const qs = params ? `?${new URLSearchParams(params).toString()}` : "";
    const res = await api.get(`/tasks${qs}`);
    return TaskListResponseSchema.parse(res);
  },

  getTask: async (id: string): Promise<TaskResponse> => {
    const res = await api.get(`/tasks/${id}`);
    return TaskResponseSchema.parse(res);
  },

  createTask: async (data: TaskCreate): Promise<TaskResponse> => {
    const res = await api.post(`/tasks`, data);
    return TaskResponseSchema.parse(res);
  },

  updateTask: async (id: string, data: TaskUpdate): Promise<TaskResponse> => {
    const res = await api.put(`/tasks/${id}`, data);
    return TaskResponseSchema.parse(res);
  },

  deleteTask: async (id: string): Promise<{ id: string; deleted: boolean }> => {
    const res = await api.delete(`/tasks/${id}`);
    return res as { id: string; deleted: boolean };
  },
};
