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
import { AlertTriangle, Info } from "lucide-react";

import { RegressionTooltipBody } from "@/components/shared/RegressionTooltipBody";
import { WarningTooltipBody } from "@/components/shared/WarningTooltipBody";
import { useRunRegressions } from "@/queries/runs";
import { formatCommit, formatCost, formatDuration, getSourceVariant, getTimeAgo } from "@/utils/formatting";
import { formatRegressionTooltip } from "../workflows/regressionBadge.utils";
import {
  formatWarningTooltip,
  shouldShowWarningBadge,
  WARNING_BADGE_CLASSES,
} from "../workflows/warningBadge.utils";

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

function WarningsCell({
  runId,
  regressionCount,
  warnings,
}: {
  runId: string;
  regressionCount: number | null | undefined;
  warnings: RunResponse["warnings"] | undefined;
}) {
  const normalizedRegressionCount = regressionCount ?? 0;
  const normalizedWarnings = warnings ?? [];
  const hasRegressions = normalizedRegressionCount > 0;
  const hasWarnings = shouldShowWarningBadge(normalizedWarnings);
  const { data: regressionData } = useRunRegressions(hasRegressions ? runId : "");

  if (!hasRegressions && !hasWarnings) {
    return <span className="text-muted">—</span>;
  }

  const regressionTooltip = regressionData?.issues?.length
    ? formatRegressionTooltip(regressionData.issues)
    : {
        header: `${normalizedRegressionCount} ${normalizedRegressionCount === 1 ? "regression" : "regressions"}`,
        lines: ["Regression detected"],
      };
  const warningTooltip = hasWarnings
    ? formatWarningTooltip(normalizedWarnings)
    : null;

  return (
    <span className="inline-flex items-center gap-2">
      {hasRegressions ? (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger
              render={
                <span className="inline-flex items-center gap-1" style={{ color: "var(--warning-11)" }}>
                  <AlertTriangle className="h-3.5 w-3.5" />
                  {normalizedRegressionCount}
                </span>
              }
            />
            <TooltipContent className="max-w-[320px] whitespace-normal px-3 py-3">
              <RegressionTooltipBody
                header={regressionTooltip.header}
                lines={regressionTooltip.lines}
              />
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      ) : null}
      {hasWarnings && warningTooltip ? (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger
              render={
                <span
                  role="status"
                  aria-label={`${normalizedWarnings.length} ${normalizedWarnings.length === 1 ? "warning" : "warnings"}`}
                  className={WARNING_BADGE_CLASSES}
                >
                  <Info aria-hidden="true" className="h-3.5 w-3.5 text-info-9" />
                  {normalizedWarnings.length}
                </span>
              }
            />
            <TooltipContent className="max-w-[320px] whitespace-normal px-3 py-3">
              <WarningTooltipBody
                header={warningTooltip.header}
                lines={warningTooltip.lines}
              />
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      ) : null}
    </span>
  );
}

export type RunRowProps = {
  run: RunResponse;
  onOpen: (runId: string) => void;
};

export function RunRow({ run, onOpen }: RunRowProps) {
  const rowHasRegression = (run.regression_count ?? 0) > 0;
  const commitSha = run.commit_sha;
  const commit = commitSha ? formatCommit(commitSha) : null;

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
        <WarningsCell
          runId={run.id}
          regressionCount={run.regression_count}
          warnings={run.warnings}
        />
      </TableCell>
      <TableCell data-type="timestamp" className={cn(RUN_TABLE_CELL_CLASS, "text-muted")}>
        {formatStartedAt(run.started_at)}
      </TableCell>
    </TableRow>
  );
}
