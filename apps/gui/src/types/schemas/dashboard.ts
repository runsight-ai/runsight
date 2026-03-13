import { z } from "zod";

export const DashboardResponseSchema = z.object({
  active_runs: z.number(),
  completed_runs: z.number(),
  total_cost_usd: z.number(),
  recent_errors: z.number(),
  system_status: z.string(),
});

export type DashboardResponse = z.infer<typeof DashboardResponseSchema>;
