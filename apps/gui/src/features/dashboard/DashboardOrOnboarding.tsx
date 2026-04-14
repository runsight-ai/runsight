import { useNavigate } from "react-router";
import { useEffect, useRef } from "react";
import { Plus, Workflow, Play } from "lucide-react";
import { PageHeader } from "@/components/shared/PageHeader";
import { EmptyState } from "@runsight/ui/empty-state";
import { Button } from "@runsight/ui/button";
import { useWorkflows, useCreateWorkflow } from "@/queries/workflows";
import { useDashboardKPIs, useAttentionItems, useRecentRuns } from "@/queries/dashboard";
import { useActiveRuns } from "@/queries/runs";
import { DashboardKPIs } from "./components/DashboardKPIs";
import { AttentionItems } from "./components/AttentionItems";
import { ActiveRunsTable } from "./components/ActiveRunsTable";

const SUBTITLE = "Here's what's happening with your workflows today.";

export function Component() {
  const navigate = useNavigate();
  const createWorkflow = useCreateWorkflow();
  const workflows = useWorkflows();
  const { activeRuns, subscribeToRunStream, isLoading, isError: isRunsError } = useActiveRuns();
  const { data, isPending, isError, refetch } = useDashboardKPIs();
  const { data: attentionData } = useAttentionItems();
  const { data: recentRunsData } = useRecentRuns(50);
  const attentionItems = attentionData?.items ?? [];
  const esRef = useRef<Map<string, EventSource>>(new Map());
  const recentRunsById = new Map((recentRunsData?.items ?? []).map((r) => [r.id, r]));

  useEffect(() => {
    const cur = esRef.current;
    for (const run of activeRuns) { if (!cur.has(run.id)) cur.set(run.id, subscribeToRunStream(run.id)); }
    for (const [id, es] of cur) { if (!activeRuns.find((r) => r.id === id)) { es.close(); cur.delete(id); } }
    return () => { for (const es of cur.values()) es.close(); cur.clear(); };
  }, [activeRuns, subscribeToRunStream]);

  async function handleNewWorkflow() {
    const result = await createWorkflow.mutateAsync({ yaml: "", commit: false });
    navigate(`/workflows/${result.id}/edit`);
  }

  const runsToday = isError ? "—" : (data?.runs_today ?? 0);
  const hasNoWorkflows = workflows.data?.items?.length === 0;
  if (hasNoWorkflows) {
    return (
      <div className="flex-1 flex flex-col">
        <PageHeader title="Home" actions={<Button onClick={handleNewWorkflow} disabled={createWorkflow.isPending}><Plus className="w-4 h-4 mr-2" />New Workflow</Button>} />
        <EmptyState icon={Workflow} title="Welcome to Runsight" description="Create your first workflow to start orchestrating AI agents." action={{ label: "Create Workflow", onClick: handleNewWorkflow }} className="flex-1" />
      </div>
    );
  }

  const headerActions = <Button onClick={handleNewWorkflow} disabled={createWorkflow.isPending}><Plus className="w-4 h-4 mr-2" />New Workflow</Button>;
  const errorBanner = (isError || isRunsError) && (
    <div className="mx-6 mt-4 p-4 rounded-md border border-border-danger bg-danger-3 text-danger-11">
      <p>Couldn't load dashboard data. Check that the Runsight server is running.</p>
      <button className="mt-2 text-sm underline" onClick={() => refetch()}>Retry</button>
    </div>
  );
  const kpiProps = { isPending, isError, runsToday, runsYesterday: data?.runs_previous_period ?? 0, costTodayUsd: isError ? "—" : (data?.cost_today_usd ?? 0), costYesterdayUsd: data?.cost_previous_period_usd ?? 0, eval_pass_rate: data?.eval_pass_rate, evalPassYesterday: data?.eval_pass_rate_previous_period, regressions: data?.regressions, regressionsYesterday: data?.regressions_previous_period };

  if (runsToday === 0) {
    return (
      <div className="flex-1 flex flex-col">
        <PageHeader title="Home" subtitle={SUBTITLE} actions={headerActions} />
        {errorBanner}
        <DashboardKPIs {...kpiProps} />
        <div className="flex-1 flex items-center justify-center px-6 pb-8">
          <EmptyState icon={Play} title="No runs yet" description="Run a workflow to see eval results, cost tracking, and regression detection here." action={{ label: "Open Flows", onClick: () => navigate("/flows") }} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col">
      <PageHeader title="Home" subtitle={SUBTITLE} actions={headerActions} />
      {errorBanner}
      <DashboardKPIs {...kpiProps} />
      <div className="space-y-6 px-6 pb-8">
        {attentionItems.length > 0 && <AttentionItems items={attentionItems} recentRunsById={recentRunsById} />}
        {(isLoading || activeRuns.length > 0) && <ActiveRunsTable runs={activeRuns} isLoading={isLoading} />}
      </div>
      <div className="flex-1" />
    </div>
  );
}
