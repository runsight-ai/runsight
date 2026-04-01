import { api } from "./client";
import { z } from "zod";
import {
  AppSettingsOutSchema,
  ModelResponseSchema,
  ProviderSummarySchema,
  SettingsBudgetListResponseSchema,
  SettingsBudgetResponseSchema,
  SettingsModelDefaultListResponseSchema,
  SettingsModelDefaultResponseSchema,
  SettingsProviderListResponseSchema,
  SettingsProviderResponseSchema,
} from "@runsight/shared/zod";
import type {
  AppSettingsOut,
  ModelDefaultUpdate,
  ModelResponse,
  ProviderCreate,
  ProviderSummary,
  ProviderUpdate,
  SettingsBudgetResponse,
  SettingsModelDefaultResponse,
  SettingsProviderResponse,
} from "@runsight/shared/zod";

export type Provider = SettingsProviderResponse;
export type CreateProvider = ProviderCreate;
export type UpdateProvider = ProviderUpdate & {
  is_active?: boolean;
};
export type ProviderCredentialTest = {
  provider_id?: string;
  provider_type?: string;
  name?: string;
  api_key_env?: string;
  base_url?: string;
};

export type ModelDefault = SettingsModelDefaultResponse;
export type UpdateModelDefault = ModelDefaultUpdate;

export type Budget = SettingsBudgetResponse;
export type CreateBudget = Partial<Budget>;
export type UpdateBudget = Partial<Budget>;

export type AppSettings = AppSettingsOut;

export const settingsApi = {
  listProviders: async (params?: Record<string, string>): Promise<{ items: Provider[]; total: number }> => {
    const qs = params ? `?${new URLSearchParams(params).toString()}` : "";
    const res = await api.get(`/settings/providers${qs}`);
    return SettingsProviderListResponseSchema.parse(res);
  },
  getProvider: async (id: string): Promise<Provider> => {
    const res = await api.get(`/settings/providers/${id}`);
    return SettingsProviderResponseSchema.parse(res);
  },
  createProvider: async (data: CreateProvider): Promise<Provider> => {
    const res = await api.post(`/settings/providers`, data);
    return SettingsProviderResponseSchema.parse(res);
  },
  updateProvider: async (id: string, data: UpdateProvider): Promise<Provider> => {
    const res = await api.put(`/settings/providers/${id}`, data);
    return SettingsProviderResponseSchema.parse(res);
  },
  deleteProvider: async (id: string): Promise<{ id: string; deleted: boolean }> => {
    const res = await api.delete<{ id: string; deleted: boolean }>(`/settings/providers/${id}`);
    return res;
  },
  testProviderConnection: async (id: string): Promise<{ success: boolean; message?: string; models?: string[] }> => {
    const res = await api.post<{ success: boolean; message?: string; models?: string[] }>(`/settings/providers/${id}/test`);
    return res;
  },
  testProviderCredentials: async (data: ProviderCredentialTest): Promise<{ success: boolean; message?: string; models?: string[] }> => {
    const res = await api.post<{ success: boolean; message?: string; models?: string[] }>(`/settings/providers/test`, data);
    return res;
  },

  listModelProviders: async (): Promise<ProviderSummary[]> => {
    const res = await api.get(`/models/providers`);
    return z.array(ProviderSummarySchema).parse(res);
  },

  listModelsForProvider: async (provider: string): Promise<ModelResponse[]> => {
    const res = await api.get(`/models?provider=${encodeURIComponent(provider)}`);
    return z.array(ModelResponseSchema).parse(res);
  },

  listModelDefaults: async (): Promise<{ items: ModelDefault[]; total: number }> => {
    const res = await api.get(`/settings/models`);
    return SettingsModelDefaultListResponseSchema.parse(res);
  },
  updateModelDefault: async (id: string, data: UpdateModelDefault): Promise<ModelDefault> => {
    const res = await api.put(`/settings/models/${id}`, data);
    return SettingsModelDefaultResponseSchema.parse(res);
  },

  getBudgets: async (): Promise<{ items: Budget[]; total: number }> => {
    const res = await api.get(`/settings/budgets`);
    return SettingsBudgetListResponseSchema.parse(res);
  },
  createBudget: async (data: CreateBudget): Promise<Budget> => {
    const res = await api.post(`/settings/budgets`, data);
    return SettingsBudgetResponseSchema.parse(res);
  },
  updateBudget: async (id: string, data: UpdateBudget): Promise<Budget> => {
    const res = await api.put(`/settings/budgets/${id}`, data);
    return SettingsBudgetResponseSchema.parse(res);
  },
  deleteBudget: async (id: string): Promise<{ id: string; deleted: boolean }> => {
    const res = await api.delete<{ id: string; deleted: boolean }>(`/settings/budgets/${id}`);
    return res;
  },

  getAppSettings: async (): Promise<AppSettings> => {
    const res = await api.get(`/settings/app`);
    return AppSettingsOutSchema.parse(res);
  },
  updateAppSettings: async (data: Partial<AppSettings>): Promise<AppSettings> => {
    const res = await api.put(`/settings/app`, data);
    return AppSettingsOutSchema.parse(res);
  },
};
