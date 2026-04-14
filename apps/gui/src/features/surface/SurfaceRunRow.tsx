import { Badge } from "@runsight/ui/badge";
import { RunStatusDot } from "@runsight/ui/RunStatusDot";
import {
  RUN_TABLE_CELL_CLASS,
  RUN_TABLE_REGRESSION_STRIPE_CLASS,
  RUN_TABLE_ROW_CLASS,
  RUN_TABLE_STATUS_CELL_CLASS,
} from "@runsight/ui/runTable.styles";
import { TableCell, TableRow } from "@runsight/ui/table";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@runsight/ui/tooltip";
import { cn } from "@runsight/ui/utils";
import type { RunResponse } from "@runsight/shared/zod";
import { AlertTriangle, Info } from "lucide-react";

import { RegressionTooltipBody } from "@/components/shared/RegressionTooltipBody";
import { WarningTooltipBody } from "@/components/shared/WarningTooltipBody";
import { useRunRegressions } from "@/queries/runs";
import { formatCost, formatDuration, getTimeAgo } from "@/utils/formatting";
import { formatRegressionTooltip } from "../workflows/regressionBadge.utils";
import {
  formatWarningTooltip,
  shouldShowWarningBadge,
  WARNING_BADGE_CLASSES,
} from "../workflows/warningBadge.utils";

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

function SurfaceWarningsCell({
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

export type SurfaceRunRowProps = {
  run: RunResponse;
  currentRunId?: string;
  onSelect: (runId: string) => void;
};

export function SurfaceRunRow({
  run,
  currentRunId,
  onSelect,
}: SurfaceRunRowProps) {
  const rowHasRegression = (run.regression_count ?? 0) > 0;

  return (
    <TableRow
      className={cn(
        RUN_TABLE_ROW_CLASS,
        currentRunId === run.id && "bg-surface-selected",
      )}
      onClick={() => onSelect(run.id)}
    >
      <TableCell
        className={cn(
          RUN_TABLE_STATUS_CELL_CLASS,
          rowHasRegression && RUN_TABLE_REGRESSION_STRIPE_CLASS,
        )}
      >
        <RunStatusDot status={run.status} className="w-full justify-center" />
      </TableCell>
      <TableCell data-type="data" className={cn(RUN_TABLE_CELL_CLASS, "text-muted")}>
        {run.run_number != null ? `#${run.run_number}` : "—"}
      </TableCell>
      <TableCell data-type="data" className={RUN_TABLE_CELL_CLASS}>
        <Badge variant={getSourceVariant(run.source)}>{run.source}</Badge>
      </TableCell>
      <TableCell data-type="timestamp" className={cn(RUN_TABLE_CELL_CLASS, "text-muted")}>
        {run.started_at ? getTimeAgo(new Date(run.started_at * 1000).toISOString()) : "—"}
      </TableCell>
      <TableCell data-type="metric" className={cn(RUN_TABLE_CELL_CLASS, "text-secondary")}>
        {formatDuration(run.duration_seconds)}
      </TableCell>
      <TableCell data-type="metric" className={cn(RUN_TABLE_CELL_CLASS, "text-success-11")}>
        {formatCost(run.total_cost_usd)}
      </TableCell>
      <TableCell data-type="metric" className={RUN_TABLE_CELL_CLASS}>
        {typeof run.eval_pass_pct === "number"
          ? `${Math.round(run.eval_pass_pct)}%`
          : typeof run.eval_score_avg === "number"
            ? run.eval_score_avg.toFixed(2)
            : <span className="text-muted">—</span>}
      </TableCell>
      <TableCell data-type="metric" className={RUN_TABLE_CELL_CLASS}>
        <SurfaceWarningsCell
          runId={run.id}
          regressionCount={run.regression_count}
          warnings={run.warnings}
        />
      </TableCell>
    </TableRow>
  );
}
