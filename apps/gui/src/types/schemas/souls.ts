import { z } from "zod";

export const SoulResponseSchema = z.object({
  id: z.string(),
  name: z.string().nullable().optional(),
  system_prompt: z.string().nullable().optional(),
  models: z.array(z.string()).nullable().optional(),
});
export type SoulResponse = z.infer<typeof SoulResponseSchema>;

export const SoulListResponseSchema = z.object({
  items: z.array(SoulResponseSchema),
  total: z.number(),
});
export type SoulListResponse = z.infer<typeof SoulListResponseSchema>;

export const SoulCreateSchema = z.object({
  id: z.string().nullable().optional(),
  name: z.string().nullable().optional(),
  system_prompt: z.string().nullable().optional(),
  models: z.array(z.string()).nullable().optional(),
});
export type SoulCreate = z.infer<typeof SoulCreateSchema>;

export const SoulUpdateSchema = z.object({
  name: z.string().nullable().optional(),
  system_prompt: z.string().nullable().optional(),
  models: z.array(z.string()).nullable().optional(),
  copy_on_edit: z.boolean().default(false),
});
export type SoulUpdate = z.infer<typeof SoulUpdateSchema>;
