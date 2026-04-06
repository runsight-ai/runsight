import { cn } from "@runsight/ui/utils";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@runsight/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@runsight/ui/tooltip";
import { AlertTriangle } from "lucide-react";
import { Badge } from "@runsight/ui/badge";
import type { RunResponse } from "@runsight/shared/zod";
import { formatCost, formatDuration, getTimeAgo } from "@/utils/formatting";
import { useRunRegressions } from "@/queries/runs";
import { formatRegressionTooltip } from "../workflows/regressionBadge.utils";
import { RunStatusDot } from "./RunStatusDot";
import {
  RUN_TABLE_CELL_CLASS,
  RUN_TABLE_CLASS,
  RUN_TABLE_CONTAINER_CLASS,
  RUN_TABLE_HEAD_CLASS,
  RUN_TABLE_HEADER_ROW_CLASS,
  RUN_TABLE_REGRESSION_STRIPE_CLASS,
  RUN_TABLE_ROW_CLASS,
  RUN_TABLE_STATUS_CELL_CLASS,
  RUN_TABLE_STATUS_HEAD_CLASS,
} from "./runTable.styles";

function getSourceVariant(source: RunResponse["source"]) {
  switch (source) {
    case "manual": return "neutral";
    case "webhook": return "info";
    case "schedule": return "accent";
    case "simulation": return "warning";
    default: return "neutral";
  }
}

function RegressionCell({ runId, regressionCount }: { runId: string; regressionCount: number | null | undefined }) {
  const { data: regressionData } = useRunRegressions(regressionCount ? runId : "");

  if (!regressionCount) {
    return <span className="text-muted">—</span>;
  }

  const tooltip = regressionData?.issues?.length
    ? formatRegressionTooltip(regressionData.issues)
    : { header: `${regressionCount} ${regressionCount === 1 ? "regression" : "regressions"}`, lines: ["Regression detected"] };

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger render={
          <span className="inline-flex items-center gap-1" style={{ color: "var(--warning-11)" }}>
            <AlertTriangle className="h-3.5 w-3.5" />
            {regressionCount}
          </span>
        } />
        <TooltipContent className="max-w-[320px] whitespace-normal px-3 py-3">
          <div className="flex items-start gap-2.5">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning-9" />
            <div className="min-w-0 text-sm">
              <p className="mb-1 font-medium text-primary">{tooltip.header}</p>
              {tooltip.lines.map((line, index) => (
                <p key={`${runId}-${index}`} className="leading-5 text-secondary">{line}</p>
              ))}
            </div>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

interface RunsTableProps {
  runs: RunResponse[];
  currentRunId?: string;
  onRowClick: (runId: string) => void;
}

export function RunsTable({ runs, currentRunId, onRowClick }: RunsTableProps) {
  if (runs.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted">
        No runs found for this workflow.
      </div>
    );
  }

  return (
    <div className={RUN_TABLE_CONTAINER_CLASS}>
      <Table className={RUN_TABLE_CLASS}>
        <TableHeader>
          <TableRow className={RUN_TABLE_HEADER_ROW_CLASS}>
            <TableHead className={cn(RUN_TABLE_HEAD_CLASS, RUN_TABLE_STATUS_HEAD_CLASS)}>
              <span className="sr-only">Status</span>
            </TableHead>
            <TableHead className={RUN_TABLE_HEAD_CLASS}>Run</TableHead>
            <TableHead className={RUN_TABLE_HEAD_CLASS}>Source</TableHead>
            <TableHead className={RUN_TABLE_HEAD_CLASS}>Started</TableHead>
            <TableHead className={RUN_TABLE_HEAD_CLASS}>Duration</TableHead>
            <TableHead className={RUN_TABLE_HEAD_CLASS}>Cost</TableHead>
            <TableHead className={RUN_TABLE_HEAD_CLASS}>Eval</TableHead>
            <TableHead className={RUN_TABLE_HEAD_CLASS}>Regr</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {runs.map((run) => {
            const rowHasRegression = (run.regression_count ?? 0) > 0;
            return (
              <TableRow
                key={run.id}
                className={cn(
                  RUN_TABLE_ROW_CLASS,
                  currentRunId === run.id && "bg-surface-selected",
                )}
                onClick={() => onRowClick(run.id)}
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
                  <RegressionCell runId={run.id} regressionCount={run.regression_count} />
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
