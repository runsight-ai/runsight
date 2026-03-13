import { z } from "zod";

export const StepResponseSchema = z.object({
  id: z.string(),
  name: z.string(),
  type: z.string(),
  path: z.string(),
  description: z.string().nullable().optional(),
});
export type StepResponse = z.infer<typeof StepResponseSchema>;

export const StepCreateSchema = z.object({
  id: z.string().nullable().optional(),
  name: z.string(),
  type: z.string().default("step"),
  description: z.string().nullable().optional(),
});
export type StepCreate = z.infer<typeof StepCreateSchema>;

export const StepUpdateSchema = z.object({
  name: z.string().nullable().optional(),
  type: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
});
export type StepUpdate = z.infer<typeof StepUpdateSchema>;

export const StepListResponseSchema = z.object({
  items: z.array(StepResponseSchema),
  total: z.number(),
});
export type StepListResponse = z.infer<typeof StepListResponseSchema>;
