import { useNavigate } from "react-router";
import { useEffect, useRef } from "react";
import { Plus } from "lucide-react";
import { PageHeader } from "@/components/shared/PageHeader";
import { Button } from "@/components/ui/button";
import { StatusDot } from "@/components/ui/status-dot";
import { StatCard } from "@/components/ui/stat-card";
import { useCreateWorkflow } from "@/queries/workflows";
import { useDashboardKPIs } from "@/queries/dashboard";
import { useActiveRuns } from "@/queries/runs";

function formatElapsed(started_at: number | null | undefined): string {
  if (!started_at) return "--";
  const elapsed = Math.floor(Date.now() / 1000 - started_at);
  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;
  return `${mins}m ${secs}s`;
}

function formatCost(total_cost_usd: number | null | undefined): string {
  if (total_cost_usd == null) return "$0.00";
  return `$${total_cost_usd.toFixed(4)}`;
}

function formatCurrency(value: number): string {
  return `$${value.toFixed(2)}`;
}

export function Component() {
  const navigate = useNavigate();
  const createWorkflow = useCreateWorkflow();
  const { activeRuns, subscribeToRunStream } = useActiveRuns();
  const { data } = useDashboardKPIs();
  const eventSourcesRef = useRef<Map<string, EventSource>>(new Map());

  // SSE: subscribe to each active run's EventSource stream
  useEffect(() => {
    const current = eventSourcesRef.current;
    for (const run of activeRuns) {
      if (!current.has(run.id)) {
        const es = subscribeToRunStream(run.id);
        current.set(run.id, es);
      }
    }
    // Cleanup stale connections
    for (const [id, es] of current) {
      if (!activeRuns.find((r) => r.id === id)) {
        es.close();
        current.delete(id);
      }
    }
    return () => {
      for (const es of current.values()) {
        es.close();
      }
      current.clear();
    };
  }, [activeRuns, subscribeToRunStream]);

  async function handleNewWorkflow() {
    const result = await createWorkflow.mutateAsync({});
    navigate(`/workflows/${result.id}/edit`);
  }

  const runsToday = data?.runs_today ?? 0;
  const costTodayUsd = data?.cost_today_usd ?? 0;
  const eval_pass_rate = data?.eval_pass_rate;
  const regressions = data?.regressions;

  const evalPassDisplay = eval_pass_rate != null ? `${(eval_pass_rate * 100).toFixed(0)}%` : "—";
  const regressionsDisplay = regressions ?? "—";

  return (
    <div className="flex-1 flex flex-col">
      <PageHeader
        title="Home"
        actions={
          <Button onClick={handleNewWorkflow} disabled={createWorkflow.isPending}>
            <Plus className="w-4 h-4 mr-2" />
            New Workflow
          </Button>
        }
      />
      <div className="grid grid-cols-4 gap-4 p-4">
        <StatCard
          label="Runs Today"
          value={runsToday}
        />
        <StatCard
          label="Eval Pass"
          value={evalPassDisplay}
        />
        <StatCard
          label="Spent Today"
          value={formatCurrency(costTodayUsd)}
        />
        <StatCard
          label="Regressions"
          value={regressionsDisplay}
          variant={regressions != null && regressions > 0 ? "warning" : "default"}
        />
      </div>

      {activeRuns.length > 0 && (
        <div className="px-6 py-4">
          <h2 className="font-mono text-xs text-muted uppercase tracking-wider mb-3">
            ACTIVE RUNS
          </h2>
          <div className="space-y-2">
            {activeRuns.map((run) => (
              <div
                key={run.id}
                className="flex items-center gap-3 px-3 py-2 rounded-md hover:bg-surface-tertiary/50 cursor-pointer"
                onClick={() => navigate(`/workflows/${run.workflow_id}/edit`)}
              >
                <StatusDot
                  variant={run.status === "running" ? "active" : "neutral"}
                  animate={run.status === "running" ? "pulse" : "none"}
                />
                <span className="text-sm font-medium flex-1 truncate">
                  {run.workflow_name}
                </span>
                <span className="text-xs text-muted">
                  {formatElapsed(run.started_at)}
                </span>
                <span className="text-xs text-muted font-mono">
                  {formatCost(run.total_cost_usd)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex-1" />
    </div>
  );
}
