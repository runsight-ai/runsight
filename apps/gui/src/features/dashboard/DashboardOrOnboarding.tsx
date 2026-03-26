import { useNavigate } from "react-router";
import { useEffect, useRef } from "react";
import { Plus, Workflow, Play, AlertTriangle } from "lucide-react";
import { PageHeader } from "@/components/shared/PageHeader";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { StatusDot } from "@/components/ui/status-dot";
import { StatCard } from "@/components/ui/stat-card";
import { Skeleton } from "@/components/ui/skeleton";
import { useWorkflows, useCreateWorkflow } from "@/queries/workflows";
import { useDashboardKPIs, useAttentionItems } from "@/queries/dashboard";
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
  const workflows = useWorkflows();
  const { activeRuns, subscribeToRunStream, isLoading, isError: isRunsError } = useActiveRuns();
  const { data, isPending, isError, error, refetch } = useDashboardKPIs();
  const { data: attentionData } = useAttentionItems();
  const attentionItems = attentionData?.items ?? [];
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

  const runsToday = isError ? "—" : (data?.runs_today ?? 0);
  const costTodayUsd = isError ? "—" : (data?.cost_today_usd ?? 0);
  const eval_pass_rate = data?.eval_pass_rate;
  const regressions = data?.regressions;

  const evalPassDisplay = isError ? "—" : (eval_pass_rate != null ? `${(eval_pass_rate * 100).toFixed(0)}%` : "—");
  const regressionsDisplay = isError ? "—" : (regressions ?? "—");

  const hasNoWorkflows = workflows.data?.items?.length === 0;

  // Priority 1: No workflows — full-page empty state
  if (hasNoWorkflows) {
    return (
      <div className="flex-1 flex flex-col">
        <PageHeader title="Home" actions={
          <Button onClick={handleNewWorkflow} disabled={createWorkflow.isPending}>
            <Plus className="w-4 h-4 mr-2" />New Workflow
          </Button>
        } />
        <EmptyState
          icon={Workflow}
          title="Welcome to Runsight"
          description="Create your first workflow to start orchestrating AI agents."
          action={{ label: "Create Workflow", onClick: handleNewWorkflow }}
          className="flex-1"
        />
      </div>
    );
  }

  const headerActions = (
    <Button onClick={handleNewWorkflow} disabled={createWorkflow.isPending}>
      <Plus className="w-4 h-4 mr-2" />New Workflow
    </Button>
  );

  const errorBanner = (isError || isRunsError) && (
    <div className="mx-4 mt-4 p-4 rounded-md border border-destructive bg-destructive/10 text-destructive">
      <p>Couldn't load dashboard data. Check that the Runsight server is running.</p>
      <button className="mt-2 text-sm underline" onClick={() => refetch()}>Retry</button>
    </div>
  );

  const kpiGrid = (
    <div className="grid grid-cols-4 gap-4 p-4">
      {isPending ? (
        <>
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </>
      ) : (
        <>
          <StatCard label="Runs Today" value={runsToday} />
          <StatCard label="Eval Pass" value={evalPassDisplay} />
          <StatCard label="Spent Today" value={typeof costTodayUsd === "string" ? costTodayUsd : formatCurrency(costTodayUsd)} />
          <StatCard label="Regressions" value={regressionsDisplay} variant={regressions != null && regressions > 0 ? "warning" : "default"} />
        </>
      )}
    </div>
  );

  // Priority 2: No runs today — KPIs with zeros + empty state
  if (runsToday === 0) {
    return (
      <div className="flex-1 flex flex-col">
        <PageHeader title="Home" actions={headerActions} />
        {errorBanner}
        {kpiGrid}
        <EmptyState
          icon={Play}
          title="No runs yet"
          description="Run a workflow to see eval results, cost tracking, and regression detection here."
          action={{ label: "Open Flows", onClick: () => navigate("/workflows") }}
        />
        <div className="flex-1" />
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col">
      <PageHeader title="Home" actions={headerActions} />
      {errorBanner}
      {kpiGrid}
      {attentionItems.length > 0 && (<div className="px-6 py-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-mono text-xs text-muted uppercase tracking-wider">ATTENTION</h2>
            {attentionItems.length > 3 && (
              <button
                className="text-xs text-muted hover:text-primary"
                onClick={() => navigate("/runs")}
              >
                see all →
              </button>
            )}
          </div>
          <div className="space-y-2">
            {attentionItems.slice(0, 3).map((item) => (
              <Card
                key={`${item.run_id}-${item.type}`}
                interactive
                className="px-4 py-3"
                onClick={() =>
                  navigate(`/workflows/${item.workflow_id}/edit`, {
                    state: { run_id: item.run_id },
                  })
                }
              >
                <div className="flex items-center gap-3">
                  {item.type !== "new_baseline" && (
                    <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0" />
                  )}
                  <Badge
                    variant={item.type === "new_baseline" ? "info" : "warning"}
                  >
                    {item.type}
                  </Badge>
                  <span className="text-sm font-medium flex-1 truncate">
                    {item.title}
                  </span>
                  <span className="text-xs text-muted truncate">
                    {item.description}
                  </span>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}
      {(isLoading || activeRuns.length > 0) && (
        <div className="px-6 py-4">
          <h2 className="font-mono text-xs text-muted uppercase tracking-wider mb-3">
            ACTIVE RUNS
          </h2>
          <div className="space-y-2">
            {isLoading ? (
              <>
                <Skeleton className="w-full h-10" />
                <Skeleton className="w-full h-10" />
              </>
            ) : (
              activeRuns.map((run) => (
                <div key={run.id} className="flex items-center gap-3 px-3 py-2 rounded-md hover:bg-surface-tertiary/50 cursor-pointer" onClick={() => navigate(`/workflows/${run.workflow_id}/edit`)}>
                  <StatusDot variant={run.status === "running" ? "active" : "neutral"} animate={run.status === "running" ? "pulse" : "none"} />
                  <span className="text-sm font-medium flex-1 truncate">{run.workflow_name}</span>
                  <span className="text-xs text-muted">{formatElapsed(run.started_at)}</span>
                  <span className="text-xs text-muted font-mono">{formatCost(run.total_cost_usd)}</span>
                </div>
              ))
            )}
          </div>
        </div>
      )}
      <div className="flex-1" />
    </div>
  );
}
