import { z } from "zod";

export const RunCreateSchema = z.object({
  workflow_id: z.string(),
  task_data: z.record(z.any()).default({}),
});
export type RunCreate = z.infer<typeof RunCreateSchema>;

export const NodeSummarySchema = z.object({
  total: z.number(),
  completed: z.number(),
  running: z.number(),
  pending: z.number(),
  failed: z.number(),
});
export type NodeSummary = z.infer<typeof NodeSummarySchema>;

export const RunResponseSchema = z.object({
  id: z.string(),
  workflow_id: z.string(),
  workflow_name: z.string(),
  status: z.string(),
  started_at: z.number().nullable().optional(),
  completed_at: z.number().nullable().optional(),
  duration_seconds: z.number().nullable().optional(),
  total_cost_usd: z.number(),
  total_tokens: z.number(),
  created_at: z.number(),
  node_summary: NodeSummarySchema.nullable().optional(),
});
export type RunResponse = z.infer<typeof RunResponseSchema>;

export const RunListResponseSchema = z.object({
  items: z.array(RunResponseSchema),
  total: z.number(),
  offset: z.number(),
  limit: z.number(),
});
export type RunListResponse = z.infer<typeof RunListResponseSchema>;

export const RunNodeResponseSchema = z.object({
  id: z.string(),
  run_id: z.string(),
  node_id: z.string(),
  block_type: z.string(),
  status: z.string(),
  started_at: z.number().nullable().optional(),
  completed_at: z.number().nullable().optional(),
  duration_seconds: z.number().nullable().optional(),
  cost_usd: z.number(),
  tokens: z.record(z.any()),
  error: z.string().nullable().optional(),
});
export type RunNodeResponse = z.infer<typeof RunNodeResponseSchema>;

export const LogResponseSchema = z.object({
  id: z.number(),
  run_id: z.string(),
  timestamp: z.number(),
  level: z.string(),
  node_id: z.string().nullable().optional(),
  message: z.string(),
});
export type LogResponse = z.infer<typeof LogResponseSchema>;

export const PaginatedLogsResponseSchema = z.object({
  items: z.array(LogResponseSchema),
  total: z.number(),
  offset: z.number(),
  limit: z.number(),
});
export type PaginatedLogsResponse = z.infer<typeof PaginatedLogsResponseSchema>;

// Additional endpoint-specific types
export const CancelRunResponseSchema = z.object({
  id: z.string(),
  status: z.string(),
});
export type CancelRunResponse = z.infer<typeof CancelRunResponseSchema>;
