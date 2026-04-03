import { z } from "zod";

export const WorkflowRegressionSchema = z.object({
  node_id: z.string(),
  node_name: z.string(),
  type: z.enum(["assertion_regression", "cost_spike", "quality_drop"]),
  delta: z.record(z.string(), z.unknown()),
  run_id: z.string().optional(),
  run_number: z.number().nullable().optional(),
});

export type WorkflowRegression = z.infer<typeof WorkflowRegressionSchema>;

export const WorkflowRegressionsResponseSchema = z.object({
  count: z.number(),
  issues: z.array(WorkflowRegressionSchema),
});

export type WorkflowRegressionsResponse = z.infer<typeof WorkflowRegressionsResponseSchema>;
