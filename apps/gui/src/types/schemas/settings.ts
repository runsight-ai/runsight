import { z } from "zod";

export const ProviderSchema = z.object({
  id: z.string(),
  name: z.string(),
  status: z.enum(["connected", "disconnected", "active", "rate-limited", "error", "unknown", "offline"]),
  api_key_env: z.string().nullish(),
  base_url: z.string().nullish(),
  models: z.array(z.string()),
  created_at: z.string().nullish(),
  updated_at: z.string().nullish(),
});
export type Provider = z.infer<typeof ProviderSchema>;

export const ModelDefaultSchema = z.object({
  id: z.string(),
  model_name: z.string(),
  provider_id: z.string(),
  provider_name: z.string(),
  fallback_chain: z.array(z.string()),
  is_default: z.boolean(),
});
export type ModelDefault = z.infer<typeof ModelDefaultSchema>;

export const BudgetSchema = z.object({
  id: z.string(),
  name: z.string(),
  limit_usd: z.number(),
  spent_usd: z.number(),
  period: z.enum(["daily", "weekly", "monthly"]),
  reset_at: z.string().optional(),
});
export type Budget = z.infer<typeof BudgetSchema>;

export const AppSettingsSchema = z.object({
  base_path: z.string().optional(),
  default_provider: z.string().optional(),
  auto_save: z.boolean().optional(),
  onboarding_completed: z.boolean().optional(),
});
export type AppSettings = z.infer<typeof AppSettingsSchema>;

export const CreateProviderSchema = z.object({
  name: z.string(),
  api_key_env: z.string().optional(),
  base_url: z.string().optional(),
});
export type CreateProvider = z.infer<typeof CreateProviderSchema>;

export const UpdateProviderSchema = CreateProviderSchema.partial().extend({
  is_active: z.boolean().optional(),
});
export type UpdateProvider = z.infer<typeof UpdateProviderSchema>;

// List responses
export const ProviderListSchema = z.object({
  items: z.array(ProviderSchema),
  total: z.number(),
});

export const ModelDefaultListSchema = z.object({
  items: z.array(ModelDefaultSchema),
  total: z.number(),
});

export const CreateBudgetSchema = z.object({
  name: z.string(),
  limit_usd: z.number(),
  period: z.enum(["daily", "weekly", "monthly"]),
});
export type CreateBudget = z.infer<typeof CreateBudgetSchema>;

export const UpdateBudgetSchema = CreateBudgetSchema.partial();
export type UpdateBudget = z.infer<typeof UpdateBudgetSchema>;

export const BudgetListSchema = z.object({
  items: z.array(BudgetSchema),
  total: z.number(),
});
