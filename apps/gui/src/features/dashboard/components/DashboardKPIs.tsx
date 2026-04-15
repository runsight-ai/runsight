import { StatCard } from "@runsight/ui/stat-card";
import { Skeleton } from "@runsight/ui/skeleton";
import {
  formatCurrency,
  formatCountDelta,
  formatCurrencyDelta,
  formatRateDelta,
  formatRegressionDelta,
  getDeltaTone,
  getRegressionDeltaTone,
  getEvalCardVariant,
} from "../utils";

interface DashboardKPIsProps {
  isPending: boolean;
  isError: boolean;
  runsToday: number | string;
  runsYesterday: number;
  costTodayUsd: number | string;
  costYesterdayUsd: number;
  eval_pass_rate: number | null | undefined;
  evalPassYesterday: number | null | undefined;
  regressions: number | null | undefined;
  regressionsYesterday: number | null | undefined;
}

export function DashboardKPIs({
  isPending, isError,
  runsToday, runsYesterday, costTodayUsd, costYesterdayUsd,
  eval_pass_rate, evalPassYesterday, regressions, regressionsYesterday,
}: DashboardKPIsProps) {
  const evalPassDisplay = isError ? "—" : (eval_pass_rate != null ? `${(eval_pass_rate * 100).toFixed(0)}%` : "—");
  const regressionsDisplay = isError ? "—" : (regressions ?? "—");
  const runsDelta = typeof runsToday === "number" ? formatCountDelta(runsToday, runsYesterday) : undefined;
  const costDelta = typeof costTodayUsd === "number" ? formatCurrencyDelta(costTodayUsd, costYesterdayUsd) : undefined;
  const evalDelta = isError ? undefined : formatRateDelta(eval_pass_rate, evalPassYesterday);
  const regressionsDelta = isError ? undefined : formatRegressionDelta(regressions, regressionsYesterday);

  return (
    <div className="grid grid-cols-1 gap-4 px-6 py-4 md:grid-cols-2 xl:grid-cols-4">
      {isPending ? (
        <><Skeleton className="h-28 w-full" /><Skeleton className="h-28 w-full" /><Skeleton className="h-28 w-full" /><Skeleton className="h-28 w-full" /></>
      ) : (
        <>
          <StatCard label="Runs Today" value={runsToday} delta={runsDelta} deltaTone="neutral" className="min-h-28 justify-between rounded-md" />
          <StatCard
            label="Eval Pass Rate" value={evalPassDisplay}
            variant={getEvalCardVariant(eval_pass_rate, evalPassYesterday)}
            delta={evalDelta}
            deltaTone={eval_pass_rate != null && evalPassYesterday != null ? getDeltaTone(eval_pass_rate, evalPassYesterday) : undefined}
            className="min-h-28 justify-between rounded-md"
          />
          <StatCard label="Cost Today" value={typeof costTodayUsd === "string" ? costTodayUsd : formatCurrency(costTodayUsd)} delta={costDelta} deltaTone="neutral" className="min-h-28 justify-between rounded-md" />
          <StatCard
            label="Regressions" value={regressionsDisplay}
            variant={regressions != null ? (regressions > 0 ? "warning" : "success") : "default"}
            delta={regressionsDelta}
            deltaTone={getRegressionDeltaTone(regressions, regressionsYesterday)}
            className="min-h-28 justify-between rounded-md"
          />
        </>
      )}
    </div>
  );
}
