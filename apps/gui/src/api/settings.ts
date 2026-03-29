import { api } from "./client";
import { z } from "zod";

const ProviderSchema = z.object({
  id: z.string(),
  name: z.string(),
  status: z.string().optional().default("connected"),
  api_key_env: z.string().nullable().optional(),
  base_url: z.string().nullable().optional(),
  models: z.array(z.string()).optional(),
  model_count: z.number().optional(),
  is_configured: z.boolean().optional(),
});
const ProviderListSchema = z.object({
  items: z.array(ProviderSchema),
  total: z.number().optional(),
}).transform(({ items, total }) => ({ items, total: total ?? items.length }));
export type Provider = z.infer<typeof ProviderSchema>;
export type CreateProvider = Pick<Provider, "name" | "api_key_env" | "base_url">;
export type UpdateProvider = Partial<CreateProvider> & {
  is_active?: boolean;
};

const ModelDefaultSchema = z.object({
  id: z.string(),
  provider_id: z.string().optional(),
  provider_name: z.string(),
  model_name: z.string(),
  is_default: z.boolean().optional().default(false),
  fallback_chain: z.array(z.string()).optional().default([]),
});
const ModelDefaultListSchema = z.object({
  items: z.array(ModelDefaultSchema),
  total: z.number().optional(),
}).transform(({ items, total }) => ({ items, total: total ?? items.length }));
export type ModelDefault = z.infer<typeof ModelDefaultSchema>;

const BudgetSchema = z.object({
  id: z.string(),
  name: z.string().optional().default("Budget"),
  limit_usd: z.number().optional().default(0),
  period: z.string().optional().default("monthly"),
});
const BudgetListSchema = z.object({
  items: z.array(BudgetSchema),
  total: z.number().optional(),
}).transform(({ items, total }) => ({ items, total: total ?? items.length }));
export type Budget = z.infer<typeof BudgetSchema>;
export type CreateBudget = Partial<Budget>;
export type UpdateBudget = Partial<Budget>;

const AppSettingsSchema = z.object({
  onboarding_completed: z.boolean().optional(),
}).passthrough();
export type AppSettings = z.infer<typeof AppSettingsSchema>;

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
