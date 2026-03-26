import { api } from "./client";
import {
  ProviderSchema,
  ProviderListSchema,
  Provider,
  CreateProvider,
  UpdateProvider,
  ModelDefaultSchema,
  ModelDefaultListSchema,
  ModelDefault,
  BudgetSchema,
  BudgetListSchema,
  Budget,
  CreateBudget,
  UpdateBudget,
  AppSettingsSchema,
  AppSettings,
} from "../types/generated/zod";

export const settingsApi = {
  listProviders: async (params?: Record<string, string>): Promise<{ items: Provider[]; total: number }> => {
    const qs = params ? `?${new URLSearchParams(params).toString()}` : "";
    const res = await api.get(`/settings/providers${qs}`);
    return ProviderListSchema.parse(res);
  },
  getProvider: async (id: string): Promise<Provider> => {
    const res = await api.get(`/settings/providers/${id}`);
    return ProviderSchema.parse(res);
  },
  createProvider: async (data: CreateProvider): Promise<Provider> => {
    const res = await api.post(`/settings/providers`, data);
    return ProviderSchema.parse(res);
  },
  updateProvider: async (id: string, data: UpdateProvider): Promise<Provider> => {
    const res = await api.put(`/settings/providers/${id}`, data);
    return ProviderSchema.parse(res);
  },
  deleteProvider: async (id: string): Promise<{ id: string; deleted: boolean }> => {
    const res = await api.delete<{ id: string; deleted: boolean }>(`/settings/providers/${id}`);
    return res;
  },
  testProviderConnection: async (id: string): Promise<{ success: boolean; message?: string; models?: string[] }> => {
    const res = await api.post<{ success: boolean; message?: string; models?: string[] }>(`/settings/providers/${id}/test`);
    return res;
  },

  listModelDefaults: async (): Promise<{ items: ModelDefault[]; total: number }> => {
    const res = await api.get(`/settings/models`);
    return ModelDefaultListSchema.parse(res);
  },
  updateModelDefault: async (id: string, data: Partial<ModelDefault>): Promise<ModelDefault> => {
    const res = await api.put(`/settings/models/${id}`, data);
    return ModelDefaultSchema.parse(res);
  },

  getBudgets: async (): Promise<{ items: Budget[]; total: number }> => {
    const res = await api.get(`/settings/budgets`);
    return BudgetListSchema.parse(res);
  },
  createBudget: async (data: CreateBudget): Promise<Budget> => {
    const res = await api.post(`/settings/budgets`, data);
    return BudgetSchema.parse(res);
  },
  updateBudget: async (id: string, data: UpdateBudget): Promise<Budget> => {
    const res = await api.put(`/settings/budgets/${id}`, data);
    return BudgetSchema.parse(res);
  },
  deleteBudget: async (id: string): Promise<{ id: string; deleted: boolean }> => {
    const res = await api.delete<{ id: string; deleted: boolean }>(`/settings/budgets/${id}`);
    return res;
  },

  getAppSettings: async (): Promise<AppSettings> => {
    const res = await api.get(`/settings/app`);
    return AppSettingsSchema.parse(res);
  },
  updateAppSettings: async (data: Partial<AppSettings>): Promise<AppSettings> => {
    const res = await api.put(`/settings/app`, data);
    return AppSettingsSchema.parse(res);
  },
};
