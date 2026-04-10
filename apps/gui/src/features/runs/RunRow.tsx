import { Badge } from "@runsight/ui/badge";
import { RunStatusDot } from "@runsight/ui/RunStatusDot";
import {
  RUN_TABLE_CELL_CLASS,
  RUN_TABLE_REGRESSION_STRIPE_CLASS,
  RUN_TABLE_ROW_CLASS,
  RUN_TABLE_STATUS_CELL_CLASS,
} from "@runsight/ui/runTable.styles";
import { cn } from "@runsight/ui/utils";
import { TableCell, TableRow } from "@runsight/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@runsight/ui/tooltip";
import type { RunResponse } from "@runsight/shared/zod";
import { AlertTriangle } from "lucide-react";

import { RegressionTooltipBody } from "@/components/shared/RegressionTooltipBody";
import { useRunRegressions } from "@/queries/runs";
import { formatCost, formatDuration, getTimeAgo } from "@/utils/formatting";
import { formatRegressionTooltip } from "../workflows/regressionBadge.utils";

function formatCommit(commitSha: string | null | undefined) {
  return commitSha ? commitSha.slice(0, 7) : null;
}

function formatRunNumber(runNumber: number | null | undefined) {
  return typeof runNumber === "number" ? `#${runNumber}` : "—";
}

function formatEval(
  evalPassPct: number | null | undefined,
  evalScoreAvg: number | null | undefined,
) {
  if (typeof evalPassPct === "number") {
    return `${Math.round(evalPassPct)}%`;
  }

  if (typeof evalScoreAvg === "number") {
    return evalScoreAvg.toFixed(2);
  }

  return "—";
}

function formatStartedAt(startedAt: number | null | undefined) {
  if (!startedAt) {
    return "—";
  }

  return getTimeAgo(new Date(startedAt * 1000).toISOString());
}

function getSourceVariant(source: RunResponse["source"]) {
  switch (source) {
    case "manual":
      return "neutral";
    case "webhook":
      return "info";
    case "schedule":
      return "accent";
    case "simulation":
      return "warning";
    default:
      return "neutral";
  }
}

function SourceBadge({ source }: { source: RunResponse["source"] }) {
  return <Badge variant={getSourceVariant(source)}>{source}</Badge>;
}

function EvalCell({
  evalPassPct,
  evalScoreAvg,
}: {
  evalPassPct: number | null | undefined;
  evalScoreAvg: number | null | undefined;
}) {
  const formattedEval = formatEval(evalPassPct, evalScoreAvg);
  if (formattedEval === "—") {
    return <span className="text-muted">—</span>;
  }

  return (
    <span className="text-primary" aria-label={formattedEval} title={formattedEval}>
      {formattedEval}
    </span>
  );
}

function RegressionCell({
  runId,
  regressionCount,
}: {
  runId: string;
  regressionCount: number | null | undefined;
}) {
  const { data: regressionData } = useRunRegressions(regressionCount ? runId : "");

  if (!regressionCount) {
    return <span className="text-muted">—</span>;
  }

  const tooltip = regressionData?.issues?.length
    ? formatRegressionTooltip(regressionData.issues)
    : {
        header: `${regressionCount} ${regressionCount === 1 ? "regression" : "regressions"}`,
        lines: ["Regression detected"],
      };

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger
          render={
            <span className="inline-flex items-center gap-1" style={{ color: "var(--warning-11)" }}>
              <AlertTriangle className="h-3.5 w-3.5" />
              {regressionCount}
            </span>
          }
        />
        <TooltipContent className="max-w-[320px] whitespace-normal px-3 py-3">
          <RegressionTooltipBody header={tooltip.header} lines={tooltip.lines} />
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

export type RunRowProps = {
  run: RunResponse;
  onOpen: (runId: string) => void;
};

export function RunRow({ run, onOpen }: RunRowProps) {
  const rowHasRegression = (run.regression_count ?? 0) > 0;
  const commit = formatCommit(run.commit_sha);

  return (
    <TableRow
      className={cn(
        RUN_TABLE_ROW_CLASS,
        run.source === "simulation" && "bg-surface-secondary text-muted",
      )}
      tabIndex={0}
      onClick={() => onOpen(run.id)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen(run.id);
        }
      }}
    >
      <TableCell
        className={cn(
          RUN_TABLE_STATUS_CELL_CLASS,
          rowHasRegression && RUN_TABLE_REGRESSION_STRIPE_CLASS,
        )}
      >
        <RunStatusDot status={run.status} className="w-full justify-center" />
      </TableCell>
      <TableCell className={RUN_TABLE_CELL_CLASS}>
        <span className="font-medium text-heading">{run.workflow_name}</span>
      </TableCell>
      <TableCell data-type="data" className={cn(RUN_TABLE_CELL_CLASS, "text-muted")}>
        {formatRunNumber(run.run_number)}
      </TableCell>
      <TableCell
        data-type="id"
        className={cn(RUN_TABLE_CELL_CLASS, "text-2xs text-muted")}
      >
        {commit ? (
          <span
            aria-label={commit}
            className="before:content-[attr(data-commit)]"
            data-commit={commit}
            title={commit}
          />
        ) : (
          <span
            aria-label="Commit unavailable"
            className="text-muted"
            title="Commit unavailable"
          >
            —
          </span>
        )}
      </TableCell>
      <TableCell data-type="data" className={RUN_TABLE_CELL_CLASS}>
        <SourceBadge source={run.source} />
      </TableCell>
      <TableCell data-type="metric" className={cn(RUN_TABLE_CELL_CLASS, "text-secondary")}>
        {formatDuration(run.duration_seconds)}
      </TableCell>
      <TableCell data-type="metric" className={cn(RUN_TABLE_CELL_CLASS, "text-success-11")}>
        {formatCost(run.total_cost_usd)}
      </TableCell>
      <TableCell data-type="metric" className={RUN_TABLE_CELL_CLASS}>
        <EvalCell
          evalPassPct={run.eval_pass_pct}
          evalScoreAvg={run.eval_score_avg}
        />
      </TableCell>
      <TableCell data-type="metric" className={RUN_TABLE_CELL_CLASS}>
        <RegressionCell runId={run.id} regressionCount={run.regression_count} />
      </TableCell>
      <TableCell data-type="timestamp" className={cn(RUN_TABLE_CELL_CLASS, "text-muted")}>
        {formatStartedAt(run.started_at)}
      </TableCell>
    </TableRow>
  );
}
