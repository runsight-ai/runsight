import type { WorkflowRegression } from "../../types/schemas/regressions";

const TYPE_LABELS: Record<string, string> = {
  assertion_regression: "Assertion",
  cost_spike: "Cost spike",
  quality_drop: "Quality drop",
  assertion: "Assertion",
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
    const label =
      TYPE_LABELS[issue.type] ?? issue.type.replaceAll("_", " ");
    const costPct =
      issue.delta?.cost_pct as number | undefined;
    const scoreDelta =
      issue.delta?.score_delta as number | undefined;
    const legacyDeltaPct =
      (issue as unknown as { delta_pct?: number }).delta_pct;

    let delta = "";
    if (typeof costPct === "number") {
      delta = ` (+${costPct.toFixed(0)}%)`;
    } else if (typeof legacyDeltaPct === "number") {
      delta = ` (+${legacyDeltaPct.toFixed(0)}%)`;
    } else if (typeof scoreDelta === "number") {
      const normalizedPct = Math.abs(scoreDelta) <= 1
        ? Math.abs(scoreDelta) * 100
        : Math.abs(scoreDelta);
      delta = ` (${normalizedPct.toFixed(0)}%)`;
    }

    return `${label}: ${issue.node_name}${delta}`;
  });

  return { header, lines };
}

export function buildRunsFilterUrl(workflowId: string): string {
  return `/runs?workflow=${encodeURIComponent(workflowId)}`;
}
