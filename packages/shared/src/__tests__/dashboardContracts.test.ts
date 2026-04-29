import { describe, expect, it } from "vitest";
import {
  AttentionItemSchema,
  AttentionItemsResponseSchema,
  DashboardKPIsResponseSchema,
} from "../zod";
import * as sharedZod from "../zod";

describe("dashboard shared response contracts", () => {
  it("parses dashboard KPI responses with nullable eval fields and period defaults", () => {
    const result = DashboardKPIsResponseSchema.safeParse({
      runs_today: 4,
      cost_today_usd: 1.25,
      eval_pass_rate: null,
      regressions: null,
    });

    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data).toMatchObject({
        runs_today: 4,
        cost_today_usd: 1.25,
        eval_pass_rate: null,
        regressions: null,
        period_hours: 24,
      });
    }
  });

  it("keeps the dashboard KPI field set stable", () => {
    expect(Object.keys(DashboardKPIsResponseSchema.shape).sort()).toEqual([
      "cost_previous_period_usd",
      "cost_today_usd",
      "eval_pass_rate",
      "eval_pass_rate_previous_period",
      "period_hours",
      "regressions",
      "regressions_previous_period",
      "runs_previous_period",
      "runs_today",
    ]);
  });

  it("does not export the retired DashboardResponseSchema", () => {
    expect("DashboardResponseSchema" in sharedZod).toBe(false);
  });

  it("parses attention items with warning and info severities", () => {
    const response = AttentionItemsResponseSchema.safeParse({
      items: [
        {
          type: "assertion_regression",
          title: "Regression detected",
          description: "Review failed on the latest run.",
          run_id: "run_dashboard_1",
          workflow_id: "wf_dashboard",
          severity: "warning",
        },
        {
          type: "new_baseline",
          title: "New baseline",
          description: "First completed run captured a baseline.",
          run_id: "run_dashboard_2",
          workflow_id: "wf_dashboard",
          severity: "info",
        },
      ],
    });

    expect(response.success).toBe(true);
    if (response.success) {
      expect(response.data.items.map((item) => item.severity)).toEqual(["warning", "info"]);
    }
  });

  it("rejects unsupported attention item types and severities", () => {
    const baseItem = {
      title: "Unexpected",
      description: "Unexpected item",
      run_id: "run_dashboard_3",
      workflow_id: "wf_dashboard",
    };

    expect(AttentionItemSchema.safeParse({
      ...baseItem,
      type: "unknown_attention_type",
      severity: "warning",
    }).success).toBe(false);
    expect(AttentionItemSchema.safeParse({
      ...baseItem,
      type: "cost_spike",
      severity: "critical",
    }).success).toBe(false);
  });
});
