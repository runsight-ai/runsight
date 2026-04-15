export function formatElapsed(started_at: number | null | undefined): string {
  if (!started_at) return "--";
  const elapsed = Math.floor(Date.now() / 1000 - started_at);
  const hours = Math.floor(elapsed / 3600);
  const mins = Math.floor((elapsed % 3600) / 60);
  const secs = elapsed % 60;
  if (hours > 0) return `${hours}:${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  return `${mins}:${String(secs).padStart(2, "0")}`;
}

export function formatCost(total_cost_usd: number | null | undefined): string {
  if (total_cost_usd == null) return "$0.00";
  return `$${total_cost_usd.toFixed(2)}`;
}

export function formatCurrency(value: number): string {
  return `$${value.toFixed(2)}`;
}

export function formatCountDelta(current: number, previous: number): string {
  const diff = current - previous;
  if (diff === 0) return "No change vs prev 24h";
  return `${diff > 0 ? "↑" : "↓"} ${Math.abs(diff)} vs prev 24h`;
}

export function formatCurrencyDelta(current: number, previous: number): string {
  const diff = current - previous;
  if (diff === 0) return "No change vs prev 24h";
  return `${diff > 0 ? "↑" : "↓"} ${formatCurrency(Math.abs(diff))} vs prev 24h`;
}

export function formatRateDelta(current: number | null | undefined, previous: number | null | undefined): string | undefined {
  if (current == null || previous == null) return undefined;
  const diff = Math.round((current - previous) * 100);
  if (diff === 0) return "No change vs prev 24h";
  return `${diff > 0 ? "↑" : "↓"} ${Math.abs(diff)} pts vs prev 24h`;
}

export function formatRegressionDelta(current: number | null | undefined, previous: number | null | undefined): string | undefined {
  if (current == null || previous == null) return undefined;
  const diff = current - previous;
  if (diff === 0) return "No change vs prev 24h";
  return `${diff > 0 ? "↑" : "↓"} ${Math.abs(diff)} vs prev 24h`;
}

export function getDeltaTone(current: number, previous: number): "positive" | "negative" | "neutral" {
  if (current === previous) return "neutral";
  return current > previous ? "positive" : "negative";
}

export function getRegressionDeltaTone(current: number | null | undefined, previous: number | null | undefined): "positive" | "negative" | "neutral" | undefined {
  if (current == null || previous == null) return undefined;
  if (current === previous) return "neutral";
  return current < previous ? "positive" : "negative";
}

const EVAL_KPI_WARNING_THRESHOLD = 0.1;
const EVAL_KPI_SUCCESS_THRESHOLD = 0.05;

export function getEvalCardVariant(current: number | null | undefined, previous: number | null | undefined): "default" | "success" | "warning" {
  if (current == null) return "default";
  if (previous != null) {
    const delta = current - previous;
    if (delta <= -EVAL_KPI_WARNING_THRESHOLD) return "warning";
    if (delta >= EVAL_KPI_SUCCESS_THRESHOLD) return "success";
  }
  return "default";
}

export function formatAttentionType(type: string): string { return type.replaceAll("_", " "); }

export function formatAttentionNodeLabel(title: string): string | null {
  const rawNode = title.split("·")[1]?.trim();
  if (!rawNode) return null;
  return rawNode.replaceAll("_", " ");
}

export function formatAttentionTitle(itemTitle: string, runInfo: { workflow_name: string; run_number?: number | null } | undefined): string {
  if (!runInfo) return itemTitle;
  if (typeof runInfo.run_number === "number") return `${runInfo.workflow_name} #${runInfo.run_number}`;
  return runInfo.workflow_name;
}

export function formatAttentionDescription(title: string, description: string): string {
  const nodeLabel = formatAttentionNodeLabel(title);
  if (!nodeLabel) return description;
  const s = nodeLabel.charAt(0).toUpperCase() + nodeLabel.slice(1);
  return `${s}: ${description}`;
}

export function formatRunStatus(status: string): string { return status.charAt(0).toUpperCase() + status.slice(1); }
export function formatRunId(runId: string): string { return runId.length > 10 ? runId.slice(-8) : runId; }
export function formatRunNumber(runNumber: number | null | undefined, runId: string): string {
  if (typeof runNumber === "number") return `#${runNumber}`;
  return `#${formatRunId(runId)}`;
}
