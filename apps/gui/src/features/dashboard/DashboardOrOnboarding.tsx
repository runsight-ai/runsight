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
import { useDashboardKPIs, useAttentionItems, useRecentRuns } from "@/queries/dashboard";
import { useActiveRuns } from "@/queries/runs";
import {
  DEFAULT_WORKFLOW_NAME,
  buildBlankWorkflowYaml,
  deriveWorkflowId,
} from "@/features/setup/workflowDraft";

const DASHBOARD_SUBTITLE = "Here's what's happening with your workflows today.";
const EVAL_KPI_WARNING_THRESHOLD = 0.1;
const EVAL_KPI_SUCCESS_THRESHOLD = 0.05;

function formatElapsed(started_at: number | null | undefined): string {
  if (!started_at) return "--";
  const elapsed = Math.floor(Date.now() / 1000 - started_at);
  const hours = Math.floor(elapsed / 3600);
  const mins = Math.floor((elapsed % 3600) / 60);
  const secs = elapsed % 60;
  if (hours > 0) {
    return `${hours}:${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }
  return `${mins}:${String(secs).padStart(2, "0")}`;
}

function formatCost(total_cost_usd: number | null | undefined): string {
  if (total_cost_usd == null) return "$0.00";
  return `$${total_cost_usd.toFixed(2)}`;
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

function getEvalCardVariant(
  current: number | null | undefined,
  previous: number | null | undefined,
): "default" | "success" | "warning" {
  if (current == null) return "default";
  if (previous != null) {
    const delta = current - previous;
    if (delta <= -EVAL_KPI_WARNING_THRESHOLD) {
      return "warning";
    }
    if (delta >= EVAL_KPI_SUCCESS_THRESHOLD) {
      return "success";
    }
  }
  return "default";
}

function formatAttentionType(type: string): string {
  return type.replaceAll("_", " ");
}

function formatAttentionNodeLabel(title: string): string | null {
  const parts = title.split("·");
  const rawNode = parts[1]?.trim();
  if (!rawNode) return null;
  return rawNode.replaceAll("_", " ");
}

function formatAttentionTitle(
  itemTitle: string,
  runInfo: { workflow_name: string; run_number?: number | null } | undefined,
): string {
  if (!runInfo) return itemTitle;
  if (typeof runInfo.run_number === "number") {
    return `${runInfo.workflow_name} #${runInfo.run_number}`;
  }
  return runInfo.workflow_name;
}

function formatAttentionDescription(title: string, description: string): string {
  const nodeLabel = formatAttentionNodeLabel(title);
  if (!nodeLabel) return description;
  const sentenceNodeLabel = nodeLabel.charAt(0).toUpperCase() + nodeLabel.slice(1);
  return `${sentenceNodeLabel}: ${description}`;
}

function formatRunStatus(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function formatRunId(runId: string): string {
  return runId.length > 10 ? runId.slice(-8) : runId;
}

function formatRunNumber(runNumber: number | null | undefined, runId: string): string {
  if (typeof runNumber === "number") {
    return `#${runNumber}`;
  }
  return `#${formatRunId(runId)}`;
}

export function Component() {
  const navigate = useNavigate();
  const createWorkflow = useCreateWorkflow();
  const workflows = useWorkflows();
  const { activeRuns, subscribeToRunStream, isLoading, isError: isRunsError } = useActiveRuns();
  const { data, isPending, isError, refetch } = useDashboardKPIs();
  const { data: attentionData } = useAttentionItems();
  const { data: recentRunsData } = useRecentRuns(50);
  const attentionItems = attentionData?.items ?? [];
  const visibleAttentionItems = attentionItems.slice(0, 3);
  const visibleActiveRuns = activeRuns.slice(0, 5);
  const eventSourcesRef = useRef<Map<string, EventSource>>(new Map());
  const recentRunsById = new Map((recentRunsData?.items ?? []).map((run) => [run.id, run]));

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
    const baseId = deriveWorkflowId(DEFAULT_WORKFLOW_NAME);
    const uniqueSuffix = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
    const workflowId = `${baseId}-${uniqueSuffix}`;
    const result = await createWorkflow.mutateAsync({
      name: DEFAULT_WORKFLOW_NAME,
      yaml: buildBlankWorkflowYaml(workflowId, DEFAULT_WORKFLOW_NAME),
      canvas_state: {
        nodes: [],
        edges: [],
        viewport: { x: 0, y: 0, zoom: 1 },
        selected_node_id: null,
        canvas_mode: "dag",
      },
      commit: false,
    });
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
            variant={getEvalCardVariant(eval_pass_rate, evalPassYesterday)}
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
        <PageHeader title="Home" subtitle={DASHBOARD_SUBTITLE} actions={headerActions} />
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
      <PageHeader title="Home" subtitle={DASHBOARD_SUBTITLE} actions={headerActions} />
      {errorBanner}
      {kpiGrid}
      <div className="space-y-6 px-6 pb-8">
        {attentionItems.length > 0 && (
          <section aria-label="Items needing attention" className="space-y-3">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-heading">
                <span className="sr-only font-mono text-xs uppercase tracking-wider text-muted">ATTENTION</span>
                Attention
              </h2>
              {attentionItems.length > 3 && (
                <button
                  className="text-sm font-medium text-interactive-default hover:text-accent-11"
                  onClick={() => navigate("/runs?attention=only")}
                >
                  see all →
                </button>
              )}
            </div>
            <div className="space-y-2">
              {visibleAttentionItems.map((item) => {
                const isInfo = item.type === "new_baseline";
                const runInfo = recentRunsById.get(item.run_id);
                return (
                  <Card
                    key={`${item.run_id}-${item.type}`}
                    interactive
                    className="rounded-md bg-surface-tertiary px-3 py-3"
                    onClick={() => navigate(`/runs/${item.run_id}`)}
                  >
                    <div className="flex items-start gap-3">
                      <div
                        className={
                          isInfo
                            ? "flex size-8 shrink-0 items-center justify-center rounded-full bg-info-3 text-info-11"
                            : "flex size-8 shrink-0 items-center justify-center rounded-full bg-warning-3 text-warning-11"
                        }
                      >
                        {isInfo ? <Activity className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-col gap-1.5 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
                          <div className="min-w-0">
                            <p className="text-sm font-medium leading-5 text-heading">
                              {formatAttentionTitle(item.title, runInfo)}
                            </p>
                            <p className="mt-0.5 line-clamp-2 text-2xs leading-5 text-muted">
                              {formatAttentionDescription(item.title, item.description)}
                            </p>
                          </div>
                          <Badge variant={isInfo ? "info" : "warning"} className="w-fit shrink-0">
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
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-heading">
                <span className="sr-only font-mono text-xs uppercase tracking-wider text-muted">ACTIVE RUNS</span>
                Active Runs
              </h2>
              {activeRuns.length > 5 && (
                <button
                  className="text-sm font-medium text-interactive-default hover:text-accent-11"
                  onClick={() => navigate("/runs?status=active")}
                >
                  see all →
                </button>
              )}
            </div>
            <Card className="overflow-hidden">
              <Table className="table-fixed">
                <colgroup>
                  <col style={{ width: "40px" }} />
                  <col style={{ width: "42%" }} />
                  <col style={{ width: "16%" }} />
                  <col style={{ width: "20%" }} />
                  <col style={{ width: "22%" }} />
                </colgroup>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="w-10">
                      <span className="sr-only">Status</span>
                    </TableHead>
                    <TableHead>Workflow</TableHead>
                    <TableHead>Run</TableHead>
                    <TableHead className="text-right">Elapsed</TableHead>
                    <TableHead className="text-right">Cost</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {isLoading ? (
                    <>
                      <TableRow className="hover:bg-transparent">
                        <TableCell colSpan={5} className="py-3">
                          <Skeleton className="h-10 w-full" />
                        </TableCell>
                      </TableRow>
                      <TableRow className="hover:bg-transparent">
                        <TableCell colSpan={5} className="py-3">
                          <Skeleton className="h-10 w-full" />
                        </TableCell>
                      </TableRow>
                    </>
                  ) : (
                    visibleActiveRuns.map((run) => (
                      <TableRow
                        key={run.id}
                        className="cursor-pointer bg-surface-primary hover:bg-surface-primary"
                        onClick={() => navigate(`/runs/${run.id}`)}
                      >
                        <TableCell className="align-middle">
                          <div className="flex items-center justify-center">
                            <StatusDot
                              variant={run.status === "running" ? "active" : "neutral"}
                              animate={run.status === "running" ? "pulse" : "none"}
                              title={formatRunStatus(run.status)}
                            />
                            <span className="sr-only">{formatRunStatus(run.status)}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <span className="font-medium text-heading">{run.workflow_name}</span>
                        </TableCell>
                        <TableCell data-type="id" className="text-muted">
                          {formatRunNumber(run.run_number, run.id)}
                        </TableCell>
                        <TableCell data-type="metric" className="text-right text-muted">
                          {formatElapsed(run.started_at)}
                        </TableCell>
                        <TableCell
                          data-type="metric"
                          className={
                            run.status === "running"
                              ? "text-right text-success-11"
                              : "text-right text-muted"
                          }
                        >
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
