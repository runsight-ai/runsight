import { useNavigate } from "react-router";
import { Plus } from "lucide-react";
import { PageHeader } from "@/components/shared/PageHeader";
import { Button } from "@/components/ui/button";
import { StatCard } from "@/components/ui/stat-card";
import { useCreateWorkflow } from "@/queries/workflows";
import { useDashboardKPIs } from "@/queries/dashboard";

function formatCurrency(value: number): string {
  return `$${value.toFixed(2)}`;
}

export function Component() {
  const navigate = useNavigate();
  const createWorkflow = useCreateWorkflow();
  const { data } = useDashboardKPIs();

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
      <div className="flex-1" />
    </div>
  );
}
