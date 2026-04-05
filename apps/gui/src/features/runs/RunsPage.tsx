import { PageHeader } from "@/components/shared";
import { EmptyState } from "@runsight/ui/empty-state";
import { Input } from "@runsight/ui/input";
import { Button } from "@runsight/ui/button";
import { Badge } from "@runsight/ui/badge";
import { Skeleton } from "@runsight/ui/skeleton";
import { cn } from "@runsight/ui/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@runsight/ui/tooltip";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@runsight/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@runsight/ui/table";
import type { RunResponse } from "@runsight/shared/zod";
import { AlertTriangle, Play, X } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { useRuns } from "@/queries/runs";
import { useAttentionItems } from "@/queries/dashboard";
import { formatCost, formatDuration, getTimeAgo } from "@/utils/formatting";
import { useRunRegressions } from "@/queries/runs";
import {
  REGRESSION_TOOLTIP_CLASSES,
} from "../workflows/regressionBadge.styles";
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

type SortColumn =
  | "status"
  | "workflow"
  | "run"
  | "commit"
  | "source"
  | "duration"
  | "cost"
  | "eval"
  | "regressions"
  | "started";
type SortDirection = "ascending" | "descending";
type SourceFilter = "production" | "all";

const PRODUCTION_RUN_SOURCES = ["manual", "webhook", "schedule"] as const;
const SOURCE_FILTER_LABELS: Record<SourceFilter, string> = {
  production: "Production runs",
  all: "All runs",
};

function RunSkeletonRow({ index }: { index: number }) {
  return (
    <tr key={index} aria-label="Loading run row">
      <td colSpan={RUN_COLUMNS.length} className="border-b border-border-subtle px-3 py-3">
        <Skeleton className="w-full" />
      </td>
    </tr>
  );
}

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

function getEvalSortValue(run: RunResponse) {
  if (typeof run.eval_pass_pct === "number") {
    return run.eval_pass_pct;
  }

  if (typeof run.eval_score_avg === "number") {
    return run.eval_score_avg * 100;
  }

  return null;
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
  regressionTypes: _regressionTypes,
}: {
  runId: string;
  regressionCount: number | null | undefined;
  regressionTypes: string[] | null | undefined;
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
        <TooltipContent className={REGRESSION_TOOLTIP_CLASSES}>
          <div className="text-xs">
            <p className="mb-1 font-medium">{tooltip.header}</p>
            {tooltip.lines.map((line, index) => (
              <p key={`${runId}-${index}`} className="text-muted">
                {line}
              </p>
            ))}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

function compareValues(
  left: string | number | null | undefined,
  right: string | number | null | undefined,
  direction: SortDirection,
) {
  if (left == null && right == null) {
    return 0;
  }

  if (left == null) {
    return 1;
  }

  if (right == null) {
    return -1;
  }

  const multiplier = direction === "ascending" ? 1 : -1;

  if (typeof left === "number" && typeof right === "number") {
    return (left - right) * multiplier;
  }

  const leftValue = left == null ? "" : String(left);
  const rightValue = right == null ? "" : String(right);
  return leftValue.localeCompare(rightValue) * multiplier;
}

function getSortValue(run: RunResponse, column: SortColumn) {
  switch (column) {
    case "status":
      return run.status;
    case "workflow":
      return run.workflow_name;
    case "run":
      return run.run_number ?? 0;
    case "commit":
      return formatCommit(run.commit_sha);
    case "source":
      return run.source;
    case "duration":
      return run.duration_seconds ?? -1;
    case "cost":
      return run.total_cost_usd ?? -1;
    case "eval":
      return getEvalSortValue(run);
    case "regressions":
      return run.regression_count;
    case "started":
      return run.started_at ?? -1;
  }
}

const RUN_COLUMNS: Array<{ key: SortColumn; label: string }> = [
  { key: "status", label: "Status" },
  { key: "workflow", label: "Workflow" },
  { key: "run", label: "Run" },
  { key: "commit", label: "Commit" },
  { key: "source", label: "Source" },
  { key: "duration", label: "Duration" },
  { key: "cost", label: "Cost" },
  { key: "eval", label: "Eval" },
  { key: "regressions", label: "Regr" },
  { key: "started", label: "Started" },
];

export function Component() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const workflowFilter = searchParams.get("workflow");
  const attentionOnly = searchParams.get("attention") === "only";
  const activeOnly = searchParams.get("status") === "active";
  const [searchQuery, setSearchQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("production");
  const [sortColumn, setSortColumn] = useState<SortColumn>("started");
  const [sortDirection, setSortDirection] = useState<SortDirection>("descending");
  const { data: attentionData } = useAttentionItems(100);
  const attentionRunIds = useMemo(
    () => new Set((attentionData?.items ?? []).map((item) => item.run_id)),
    [attentionData?.items],
  );

  const queryParams = useMemo(() => {
    const params: Record<string, string | string[]> =
      sourceFilter === "all" ? {} : { source: [...PRODUCTION_RUN_SOURCES] };

    if (workflowFilter) {
      params.workflow_id = workflowFilter;
    }

    if (activeOnly) {
      params.status = ["running", "pending"];
      params.branch = "main";
    }

    if (attentionOnly) {
      params.limit = "100";
    }

    return Object.keys(params).length > 0 ? params : undefined;
  }, [activeOnly, attentionOnly, sourceFilter, workflowFilter]);
  const { data, isLoading, error, refetch } = useRuns(queryParams);
  const visibleColumns = RUN_COLUMNS;

  const runs = useMemo(() => data?.items ?? [], [data?.items]);
  const filteredWorkflowName = workflowFilter
    ? runs[0]?.workflow_name ?? workflowFilter
    : null;

  const clearFilters = () => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("workflow");
      next.delete("attention");
      next.delete("status");
      return next;
    });
  };

  const setAttentionFilter = (enabled: boolean) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (enabled) {
        next.set("attention", "only");
      } else {
        next.delete("attention");
      }
      return next;
    });
  };

  const setActiveFilter = (enabled: boolean) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (enabled) {
        next.set("status", "active");
      } else {
        next.delete("status");
      }
      return next;
    });
  };

  const filteredRuns = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLowerCase();
    const matchingRuns = normalizedQuery
      ? runs.filter((run) => run.workflow_name.toLowerCase().includes(normalizedQuery))
      : runs;
    const attentionFilteredRuns = attentionOnly
      ? matchingRuns.filter((run) => attentionRunIds.has(run.id))
      : matchingRuns;

    return [...attentionFilteredRuns].sort((left, right) =>
      compareValues(
        getSortValue(left, sortColumn),
        getSortValue(right, sortColumn),
        sortDirection,
      ),
    );
  }, [attentionOnly, attentionRunIds, runs, searchQuery, sortColumn, sortDirection]);

  const handleSort = (column: SortColumn) => {
    if (column === sortColumn) {
      setSortDirection((current) =>
        current === "ascending" ? "descending" : "ascending",
      );
      return;
    }

    setSortColumn(column);
    setSortDirection("ascending");
  };

  const getAriaSort = (column: SortColumn) =>
    column === sortColumn ? sortDirection : "none";

  const openRun = (runId: string) => {
    navigate(`/runs/${runId}`);
  };

  return (
    <div className="flex h-full flex-col bg-surface-primary">
      <PageHeader
        title={
          filteredWorkflowName
            ? `Runs \u2014 ${filteredWorkflowName}`
            : attentionOnly
              ? "Runs \u2014 Attention"
              : activeOnly
                ? "Runs \u2014 Active"
                : "Runs"
        }
        actions={
          filteredWorkflowName || attentionOnly || activeOnly ? (
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label="Clear run filters"
              onClick={clearFilters}
            >
              <X className="h-4 w-4" />
            </Button>
          ) : undefined
        }
      />

      <main className="flex-1 overflow-auto px-6 pb-6">
        <section className="flex h-full flex-col py-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center">
            <div className="max-w-md flex-1">
              <Input
                type="search"
                autoFocus
                aria-label="Search runs"
                placeholder="Search runs..."
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
              />
            </div>
            <div className="w-full md:w-48">
              <Select
                value={sourceFilter}
                onValueChange={(value) => setSourceFilter(value as SourceFilter)}
              >
                <SelectTrigger aria-label="Filter runs by source">
                  <span className="flex flex-1 text-left">
                    {SOURCE_FILTER_LABELS[sourceFilter]}
                  </span>
                </SelectTrigger>
                <SelectContent align="end" sideOffset={8}>
                  <SelectItem value="production">Production runs</SelectItem>
                  <SelectItem value="all">All runs</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button
              type="button"
              variant={activeOnly ? "secondary" : "ghost"}
              aria-pressed={activeOnly}
              onClick={() => setActiveFilter(!activeOnly)}
              className="w-full md:w-auto"
            >
              Active
            </Button>
            <Button
              type="button"
              variant={attentionOnly ? "secondary" : "ghost"}
              aria-pressed={attentionOnly}
              onClick={() => setAttentionFilter(!attentionOnly)}
              className="w-full md:w-auto"
            >
              Needs attention
            </Button>
          </div>

          <div className="flex-1 pt-4">
            {isLoading ? (
              <div className="overflow-hidden rounded-lg border border-border-default bg-surface-secondary">
                <Table>
                  <TableBody>
                    {Array.from({ length: 5 }, (_, index) => (
                      <RunSkeletonRow key={index} index={index} />
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : error ? (
              <section className="flex flex-col items-center justify-center gap-3 px-4 py-12 text-center">
                <h2>Couldn&apos;t load runs.</h2>
                <Button type="button" onClick={() => refetch()}>
                  Retry
                </Button>
              </section>
            ) : runs.length === 0 ? (
              <EmptyState
                icon={Play}
                title="No runs yet"
                description="Run a workflow to see execution history here."
                action={{ label: "Go to Workflows", onClick: () => navigate("/flows") }}
              />
            ) : filteredRuns.length === 0 ? (
              <EmptyState
                icon={Play}
                title={attentionOnly ? "No runs need attention" : "No matching runs"}
                description={
                  attentionOnly
                    ? "Production runs with dashboard attention items will appear here."
                    : "Try another workflow name."
                }
              />
            ) : (
              <div className={RUN_TABLE_CONTAINER_CLASS}>
                <Table className={RUN_TABLE_CLASS}>
                  <TableHeader>
                    <TableRow className={cn("bg-surface-primary", RUN_TABLE_HEADER_ROW_CLASS)}>
                      {visibleColumns.map((column) => (
                        <TableHead
                          key={column.key}
                          aria-sort={getAriaSort(column.key)}
                          onClick={() => handleSort(column.key)}
                          className={cn(
                            RUN_TABLE_HEAD_CLASS,
                            column.key === "status" && RUN_TABLE_STATUS_HEAD_CLASS,
                          )}
                        >
                          {column.label}
                        </TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredRuns.map((run) => {
                      const rowHasRegression = (run.regression_count ?? 0) > 0;

                      return (
                        <TableRow
                          key={run.id}
                          className={cn(
                            RUN_TABLE_ROW_CLASS,
                            run.source === "simulation" && "bg-surface-secondary text-muted",
                          )}
                          tabIndex={0}
                          onClick={() => openRun(run.id)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              openRun(run.id);
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
                            <span className="font-medium text-heading">
                              {run.workflow_name}
                            </span>
                          </TableCell>
                          <TableCell data-type="data" className={cn(RUN_TABLE_CELL_CLASS, "text-muted")}>
                            {formatRunNumber(run.run_number)}
                          </TableCell>
                          <TableCell
                            data-type="id"
                            className={cn(RUN_TABLE_CELL_CLASS, "text-2xs text-muted")}
                          >
                            {formatCommit(run.commit_sha) ? (
                              <span
                                aria-label={formatCommit(run.commit_sha) ?? undefined}
                                className="before:content-[attr(data-commit)]"
                                data-commit={formatCommit(run.commit_sha) ?? ""}
                                title={formatCommit(run.commit_sha) ?? undefined}
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
                            <RegressionCell
                              runId={run.id}
                              regressionCount={run.regression_count}
                              regressionTypes={run.regression_types}
                            />
                          </TableCell>
                          <TableCell
                            data-type="timestamp"
                            className={cn(RUN_TABLE_CELL_CLASS, "text-muted")}
                          >
                            {formatStartedAt(run.started_at)}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
