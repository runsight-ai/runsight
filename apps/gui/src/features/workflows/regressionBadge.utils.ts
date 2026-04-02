import type { WorkflowRegression } from "../../types/schemas/regressions";

const TYPE_LABELS: Record<WorkflowRegression["type"], string> = {
  assertion: "Assertion",
  cost_spike: "Cost spike",
  latency_spike: "Latency spike",
};

export function shouldShowRegressionBadge(
  issues: WorkflowRegression[] | undefined,
): boolean {
  return Array.isArray(issues) && issues.length > 0;
}

export function formatRegressionTooltip(issues: WorkflowRegression[]): {
  header: string;
  lines: string[];
} {
  const count = issues.length;
  const header = `${count} ${count === 1 ? "regression" : "regressions"}`;

  const lines = issues.map((issue) => {
    const label = TYPE_LABELS[issue.type];
    const delta = issue.delta_pct != null ? ` (+${issue.delta_pct}%)` : "";
    return `${label}: ${issue.node_name}${delta}`;
  });

  return { header, lines };
}

export function buildRunsFilterUrl(workflowId: string): string {
  return `/runs?workflow=${encodeURIComponent(workflowId)}`;
}
