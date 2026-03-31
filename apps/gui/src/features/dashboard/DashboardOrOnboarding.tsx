import { useNavigate } from "react-router";
import { useEffect, useRef } from "react";
import { Plus, Workflow, Play, AlertTriangle, Activity } from "lucide-react";
import { PageHeader } from "@/components/shared/PageHeader";
import { EmptyState } from "@runsight/ui/empty-state";
import { Button } from "@runsight/ui/button";
import { Badge } from "@runsight/ui/badge";
import { Card } from "@runsight/ui/card";
import { StatusDot } from "@runsight/ui/status-dot";
import { StatCard } from "@runsight/ui/stat-card";
import { Skeleton } from "@runsight/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@runsight/ui/table";
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

function formatCountDelta(current: number, previous: number): string {
  const diff = current - previous;
  if (diff === 0) return "No change vs prev 24h";
  return `${diff > 0 ? "↑" : "↓"} ${Math.abs(diff)} vs prev 24h`;
}

function formatCurrencyDelta(current: number, previous: number): string {
  const diff = current - previous;
  if (diff === 0) return "No change vs prev 24h";
  return `${diff > 0 ? "↑" : "↓"} ${formatCurrency(Math.abs(diff))} vs prev 24h`;
}

function formatRateDelta(current: number | null | undefined, previous: number | null | undefined): string | undefined {
  if (current == null || previous == null) return undefined;
  const diff = Math.round((current - previous) * 100);
  if (diff === 0) return "No change vs prev 24h";
  return `${diff > 0 ? "↑" : "↓"} ${Math.abs(diff)} pts vs prev 24h`;
}

function formatRegressionDelta(current: number | null | undefined, previous: number | null | undefined): string | undefined {
  if (current == null || previous == null) return undefined;
  const diff = current - previous;
  if (diff === 0) return "No change vs prev 24h";
  return `${diff > 0 ? "↑" : "↓"} ${Math.abs(diff)} vs prev 24h`;
}

function getDeltaTone(current: number, previous: number): "positive" | "negative" | "neutral" {
  if (current === previous) return "neutral";
  return current > previous ? "positive" : "negative";
}

function getRegressionDeltaTone(
  current: number | null | undefined,
  previous: number | null | undefined,
): "positive" | "negative" | "neutral" | undefined {
  if (current == null || previous == null) return undefined;
  if (current === previous) return "neutral";
  return current < previous ? "positive" : "negative";
}

function formatAttentionType(type: string): string {
  return type.replaceAll("_", " ");
}

function formatRunStatus(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function formatRunId(runId: string): string {
  return runId.length > 10 ? runId.slice(-8) : runId;
}

export function Component() {
  const navigate = useNavigate();
  const createWorkflow = useCreateWorkflow();
  const workflows = useWorkflows();
  const { activeRuns, subscribeToRunStream, isLoading, isError: isRunsError } = useActiveRuns();
  const { data, isPending, isError, refetch } = useDashboardKPIs();
  const { data: attentionData } = useAttentionItems();
  const attentionItems = attentionData?.items ?? [];
  const visibleAttentionItems = attentionItems.slice(0, 3);
  const visibleActiveRuns = activeRuns.slice(0, 5);
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
  const runsYesterday = data?.runs_previous_period ?? 0;
  const costYesterdayUsd = data?.cost_previous_period_usd ?? 0;
  const evalPassYesterday = data?.eval_pass_rate_previous_period;
  const regressionsYesterday = data?.regressions_previous_period;

  const evalPassDisplay = isError ? "—" : (eval_pass_rate != null ? `${(eval_pass_rate * 100).toFixed(0)}%` : "—");
  const regressionsDisplay = isError ? "—" : (regressions ?? "—");
  const runsDelta = typeof runsToday === "number" ? formatCountDelta(runsToday, runsYesterday) : undefined;
  const costDelta =
    typeof costTodayUsd === "number" ? formatCurrencyDelta(costTodayUsd, costYesterdayUsd) : undefined;
  const evalDelta = isError ? undefined : formatRateDelta(eval_pass_rate, evalPassYesterday);
  const regressionsDelta = isError ? undefined : formatRegressionDelta(regressions, regressionsYesterday);

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
    <div className="mx-6 mt-4 p-4 rounded-md border border-border-danger bg-danger-3 text-danger-11">
      <p>Couldn't load dashboard data. Check that the Runsight server is running.</p>
      <button className="mt-2 text-sm underline" onClick={() => refetch()}>Retry</button>
    </div>
  );

  const kpiGrid = (
    <div className="grid grid-cols-1 gap-4 px-6 py-4 md:grid-cols-2 xl:grid-cols-4">
      {isPending ? (
        <>
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
        </>
      ) : (
        <>
          <StatCard
            label="Runs Today"
            value={runsToday}
            delta={runsDelta}
            deltaTone="neutral"
            className="min-h-28 justify-between rounded-md"
          />
          <StatCard
            label="Eval Pass Rate"
            value={evalPassDisplay}
            variant={eval_pass_rate != null && eval_pass_rate >= 0.8 ? "success" : "default"}
            delta={evalDelta}
            deltaTone={
              eval_pass_rate != null && evalPassYesterday != null
                ? getDeltaTone(eval_pass_rate, evalPassYesterday)
                : undefined
            }
            className="min-h-28 justify-between rounded-md"
          />
          <StatCard
            label="Cost Today"
            value={typeof costTodayUsd === "string" ? costTodayUsd : formatCurrency(costTodayUsd)}
            delta={costDelta}
            deltaTone="neutral"
            className="min-h-28 justify-between rounded-md"
          />
          <StatCard
            label="Regressions"
            value={regressionsDisplay}
            variant={regressions != null ? (regressions > 0 ? "warning" : "success") : "default"}
            delta={regressionsDelta}
            deltaTone={getRegressionDeltaTone(regressions, regressionsYesterday)}
            className="min-h-28 justify-between rounded-md"
          />
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
        <div className="flex-1 flex items-center justify-center px-6 pb-8">
          <EmptyState
            icon={Play}
            title="No runs yet"
            description="Run a workflow to see eval results, cost tracking, and regression detection here."
            action={{ label: "Open Flows", onClick: () => navigate("/flows") }}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col">
      <PageHeader title="Home" actions={headerActions} />
      {errorBanner}
      {kpiGrid}
      <div className="space-y-6 px-6 pb-8">
        {attentionItems.length > 0 && (
          <section aria-label="Items needing attention" className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="font-mono text-xs text-muted uppercase tracking-wider">ATTENTION</h2>
              {attentionItems.length > 3 && (
                <button
                  className="text-xs text-muted hover:text-primary"
                  onClick={() => navigate("/runs?attention=only")}
                >
                  see all →
                </button>
              )}
            </div>
            <div className="space-y-2">
              {visibleAttentionItems.map((item) => {
                const isInfo = item.type === "new_baseline";
                return (
                  <Card
                    key={`${item.run_id}-${item.type}`}
                    interactive
                    className="px-3 py-3"
                    onClick={() => navigate(`/runs/${item.run_id}`)}
                  >
                    <div className="flex items-start gap-3">
                      <div className={isInfo ? "mt-0.5 text-info-11" : "mt-0.5 text-warning-11"}>
                        {isInfo ? (
                          <Activity className="h-4 w-4" />
                        ) : (
                          <AlertTriangle className="h-4 w-4" />
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-col gap-1.5 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
                          <div className="min-w-0">
                            <p className="text-sm font-medium leading-5 text-heading">{item.title}</p>
                            <p className="mt-1 line-clamp-2 text-sm leading-5 text-secondary">{item.description}</p>
                          </div>
                          <Badge variant={isInfo ? "info" : "warning"} className="w-fit">
                            {formatAttentionType(item.type)}
                          </Badge>
                        </div>
                      </div>
                    </div>
                  </Card>
                );
              })}
            </div>
          </section>
        )}
        {(isLoading || activeRuns.length > 0) && (
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="font-mono text-xs text-muted uppercase tracking-wider">
                ACTIVE RUNS
              </h2>
              {activeRuns.length > 5 && (
                <button
                  className="text-xs text-muted hover:text-primary"
                  onClick={() => navigate("/runs?status=active")}
                >
                  see all →
                </button>
              )}
            </div>
            <Card className="overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead>Workflow</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Elapsed</TableHead>
                    <TableHead className="text-right">Cost</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {isLoading ? (
                    <>
                      <TableRow className="hover:bg-transparent">
                        <TableCell colSpan={4} className="py-3">
                          <Skeleton className="h-10 w-full" />
                        </TableCell>
                      </TableRow>
                      <TableRow className="hover:bg-transparent">
                        <TableCell colSpan={4} className="py-3">
                          <Skeleton className="h-10 w-full" />
                        </TableCell>
                      </TableRow>
                    </>
                  ) : (
                    visibleActiveRuns.map((run) => (
                      <TableRow
                        key={run.id}
                        className="cursor-pointer"
                        onClick={() =>
                          navigate(`/workflows/${run.workflow_id}/edit`, {
                            state: { run_id: run.id },
                          })
                        }
                      >
                        <TableCell>
                          <div className="flex flex-col gap-1">
                            <span className="text-sm font-medium text-heading">{run.workflow_name}</span>
                            <span className="font-mono text-xs text-muted">
                              Run {formatRunId(run.id)}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="inline-flex items-center gap-2">
                            <StatusDot
                              variant={run.status === "running" ? "active" : "neutral"}
                              animate={run.status === "running" ? "pulse" : "none"}
                            />
                            <span className="text-sm text-primary">{formatRunStatus(run.status)}</span>
                          </div>
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm text-muted">
                          {formatElapsed(run.started_at)}
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm text-muted">
                          {formatCost(run.total_cost_usd)}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </Card>
          </section>
        )}
      </div>
      <div className="flex-1" />
    </div>
  );
}
