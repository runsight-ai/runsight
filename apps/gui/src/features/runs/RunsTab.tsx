import { EmptyState } from "@runsight/ui/empty-state";
import { Input } from "@runsight/ui/input";
import { Button } from "@runsight/ui/button";
import {
  RUN_TABLE_CLASS,
  RUN_TABLE_CONTAINER_CLASS,
  RUN_TABLE_HEAD_CLASS,
  RUN_TABLE_HEADER_ROW_CLASS,
  RUN_TABLE_STATUS_HEAD_CLASS,
} from "@runsight/ui/runTable.styles";
import { Skeleton } from "@runsight/ui/skeleton";
import { cn } from "@runsight/ui/utils";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@runsight/ui/select";
import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
} from "@runsight/ui/table";
import type { RunResponse } from "@runsight/shared/zod";
import { Play } from "lucide-react";
import { type ComponentType, useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { useRuns } from "@/queries/runs";
import { useWorkflows } from "@/queries/workflows";
import type { RunRowProps } from "./RunRow";

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

function getEvalSortValue(run: RunResponse) {
  if (typeof run.eval_pass_pct === "number") {
    return run.eval_pass_pct;
  }

  if (typeof run.eval_score_avg === "number") {
    return run.eval_score_avg * 100;
  }

  return null;
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
      return run.commit_sha?.slice(0, 7) ?? null;
    case "source":
      return run.source;
    case "duration":
      return run.duration_seconds ?? -1;
    case "cost":
      return run.total_cost_usd ?? -1;
    case "eval":
      return getEvalSortValue(run);
    case "regressions":
      return (run.regression_count ?? 0) + (run.warnings?.length ?? 0);
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
  { key: "regressions", label: "Warnings" },
  { key: "started", label: "Started" },
];

type RunsTabProps = {
  RowComponent: ComponentType<RunRowProps>;
  workflowFilter: string | null;
  attentionOnly: boolean;
  activeOnly: boolean;
  onWorkflowFilterChange: (workflowId: string | null) => void;
  onAttentionFilterChange: (enabled: boolean) => void;
  onActiveFilterChange: (enabled: boolean) => void;
  onClearFilters: () => void;
};

export function RunsTab({
  RowComponent,
  workflowFilter,
  attentionOnly,
  activeOnly,
  onWorkflowFilterChange,
  onAttentionFilterChange,
  onActiveFilterChange,
  onClearFilters,
}: RunsTabProps) {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("all");
  const [sortColumn, setSortColumn] = useState<SortColumn>("started");
  const [sortDirection, setSortDirection] = useState<SortDirection>("descending");
  const { data: workflowsData } = useWorkflows();
  const workflows = useMemo(() => workflowsData?.items ?? [], [workflowsData?.items]);

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

    return Object.keys(params).length > 0 ? params : undefined;
  }, [activeOnly, sourceFilter, workflowFilter]);
  const { data, isLoading, error, refetch } = useRuns(queryParams);
  const visibleColumns = RUN_COLUMNS;

  const runs = useMemo(() => data?.items ?? [], [data?.items]);

  const filteredRuns = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLowerCase();
    const matchingRuns = normalizedQuery
      ? runs.filter((run) => run.workflow_name.toLowerCase().includes(normalizedQuery))
      : runs;
    const attentionFilteredRuns = attentionOnly
      ? matchingRuns.filter(
          (run) => (run.regression_count ?? 0) + (run.warnings?.length ?? 0) > 0,
        )
      : matchingRuns;

    return [...attentionFilteredRuns].sort((left, right) =>
      compareValues(
        getSortValue(left, sortColumn),
        getSortValue(right, sortColumn),
        sortDirection,
      ),
    );
  }, [attentionOnly, runs, searchQuery, sortColumn, sortDirection]);

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
    <>
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
            value={workflowFilter ?? "all"}
            onValueChange={onWorkflowFilterChange}
          >
            <SelectTrigger aria-label="Filter runs by workflow">
              <span className="flex flex-1 truncate text-left">
                {workflowFilter
                  ? workflows.find((w) => w.id === workflowFilter)?.name ?? workflowFilter
                  : "All workflows"}
              </span>
            </SelectTrigger>
            <SelectContent align="end" sideOffset={8}>
              <SelectItem value="all">All workflows</SelectItem>
              {workflows.map((w) => (
                <SelectItem key={w.id} value={w.id}>
                  {w.name ?? w.id}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
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
          onClick={() => onActiveFilterChange(!activeOnly)}
          className="w-full md:w-auto"
        >
          Active
        </Button>
        <Button
          type="button"
          variant={attentionOnly ? "secondary" : "ghost"}
          aria-pressed={attentionOnly}
          onClick={() => onAttentionFilterChange(!attentionOnly)}
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
        ) : runs.length === 0 && !workflowFilter && !activeOnly ? (
          <EmptyState
            icon={Play}
            title="No runs yet"
            description="Run a workflow to see execution history here."
            action={{ label: "Go to Workflows", onClick: () => navigate("/flows") }}
          />
        ) : filteredRuns.length === 0 ? (
          <EmptyState
            icon={Play}
            title={
              attentionOnly
                ? "No runs need attention"
                : activeOnly
                  ? "No active runs"
                  : "No matching runs"
            }
            description={
              attentionOnly
                ? "No runs with warnings or regressions found."
                : activeOnly
                  ? "No runs are currently in progress."
                  : "Try adjusting your filters."
            }
            action={{ label: "Clear filters", onClick: onClearFilters }}
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
                      aria-label={column.key === "status" ? "Status" : column.label}
                      onClick={() => handleSort(column.key)}
                      className={cn(
                        RUN_TABLE_HEAD_CLASS,
                        column.key === "status" && RUN_TABLE_STATUS_HEAD_CLASS,
                      )}
                    >
                      {column.key === "status" ? (
                        <span className="sr-only">Status</span>
                      ) : (
                        column.label
                      )}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredRuns.map((run) => (
                  <RowComponent
                    key={run.id}
                    run={run}
                    onOpen={openRun}
                  />
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </>
  );
}
