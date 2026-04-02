import { z } from "zod";

export const WorkflowRegressionSchema = z.object({
  type: z.enum(["assertion", "cost_spike", "latency_spike"]),
  node_name: z.string(),
  delta_pct: z.number().optional(),
});

export type WorkflowRegression = z.infer<typeof WorkflowRegressionSchema>;

export const WorkflowRegressionsResponseSchema = z.object({
  workflow_id: z.string(),
  items: z.array(WorkflowRegressionSchema),
  count: z.number(),
});

export type WorkflowRegressionsResponse = z.infer<typeof WorkflowRegressionsResponseSchema>;
