import { z } from "zod";

export const WorkflowResponseSchema = z.object({
  id: z.string(),
  name: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
  blocks: z.record(z.any()).default({}),
  edges: z.array(z.record(z.any())).default([]),
  status: z.string().optional(),
  updated_at: z.string().optional(),
  created_at: z.string().optional(),
  last_run_duration: z.number().optional(),
  last_run_cost_usd: z.number().optional(),
  last_run_completed_at: z.string().optional(),
  step_count: z.number().optional(),
  block_count: z.number().optional(),
});
export type WorkflowResponse = z.infer<typeof WorkflowResponseSchema>;

export const WorkflowListResponseSchema = z.object({
  items: z.array(WorkflowResponseSchema),
  total: z.number(),
});
export type WorkflowListResponse = z.infer<typeof WorkflowListResponseSchema>;

export const WorkflowCreateSchema = z.object({
  id: z.string().optional(),
  name: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
  blocks: z.record(z.any()).default({}),
  edges: z.array(z.record(z.any())).default([]),
});
export type WorkflowCreate = z.infer<typeof WorkflowCreateSchema>;

export const WorkflowUpdateSchema = z.object({
  name: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
  blocks: z.record(z.any()).nullable().optional(),
  edges: z.array(z.record(z.any())).nullable().optional(),
});
export type WorkflowUpdate = z.infer<typeof WorkflowUpdateSchema>;
