import { EmptyState } from "@runsight/ui/empty-state";
import { Input } from "@runsight/ui/input";
import { Button } from "@runsight/ui/button";
import { Badge, BadgeDot } from "@runsight/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@runsight/ui/table";
import type { RunResponse } from "@runsight/shared/zod";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { useRuns } from "@/queries/runs";
import { formatCost, formatDuration, getTimeAgo } from "@/utils/formatting";

type SortColumn =
  | "status"
  | "workflow"
  | "run"
  | "commit"
  | "duration"
  | "cost"
  | "eval"
  | "started";
type SortDirection = "ascending" | "descending";

const PRODUCTION_RUN_SOURCES = ["manual", "webhook", "schedule"] as const;

function getRunStatusVariant(status: string) {
  switch (status.toLowerCase()) {
    case "completed":
    case "success":
      return "success";
    case "failed":
    case "killed":
      return "danger";
    case "running":
      return "info";
    case "partial":
    case "paused":
    case "stalled":
      return "warning";
    default:
      return "neutral";
  }
}

function EmptyIcon() {
  return null;
}

function RunSkeletonRow({ index }: { index: number }) {
  return (
    <tr key={index} aria-label="Loading run row">
      <td colSpan={8} className="border-b border-border-subtle px-3 py-3">
        <div className="h-4 w-full animate-pulse rounded bg-border-default" />
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

function formatEval(evalPassPct: number | null | undefined) {
  if (typeof evalPassPct !== "number") {
    return "—";
  }

  return `${Math.round(evalPassPct)}%`;
}

function formatStartedAt(startedAt: number | null | undefined) {
  if (!startedAt) {
    return "—";
  }

  return getTimeAgo(new Date(startedAt * 1000).toISOString());
}

function EvalCell({ evalPassPct }: { evalPassPct: number | null | undefined }) {
  if (typeof evalPassPct !== "number") {
    return <>—</>;
  }

  const formattedEval = formatEval(evalPassPct);

  if (evalPassPct >= 90) {
    return <Badge variant="success">{formattedEval}</Badge>;
  }

  return (
    <Badge
      variant="warning"
      aria-label={formattedEval}
      title={formattedEval}
    >
      <span
        aria-hidden="true"
        className="before:content-[attr(data-eval)]"
        data-eval={formattedEval}
      />
    </Badge>
  );
}

function compareValues(
  left: string | number | null | undefined,
  right: string | number | null | undefined,
  direction: SortDirection,
) {
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
    case "duration":
      return run.duration_seconds ?? -1;
    case "cost":
      return run.total_cost_usd ?? -1;
    case "eval":
      return run.eval_pass_pct ?? -1;
    case "started":
      return run.started_at ?? -1;
  }
}

const RUN_COLUMNS: Array<{ key: SortColumn; label: string }> = [
  { key: "status", label: "Status" },
  { key: "workflow", label: "Workflow" },
  { key: "run", label: "Run" },
  { key: "commit", label: "Commit" },
  { key: "duration", label: "Duration" },
  { key: "cost", label: "Cost" },
  { key: "eval", label: "Eval" },
  { key: "started", label: "Started" },
];

interface RunsTabProps {
  onGoToWorkflows: () => void;
}

export function Component({ onGoToWorkflows }: RunsTabProps) {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState("");
  const [sortColumn, setSortColumn] = useState<SortColumn>("started");
  const [sortDirection, setSortDirection] = useState<SortDirection>("descending");

  const queryParams = useMemo(
    () => ({ source: [...PRODUCTION_RUN_SOURCES] }),
    [],
  );
  const { data, isLoading, error, refetch } = useRuns(queryParams);

  const runs = useMemo(() => data?.items ?? [], [data?.items]);
  const filteredRuns = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLowerCase();
    const matchingRuns = normalizedQuery
      ? runs.filter((run) => run.workflow_name.toLowerCase().includes(normalizedQuery))
      : runs;

    return [...matchingRuns].sort((left, right) =>
      compareValues(
        getSortValue(left, sortColumn),
        getSortValue(right, sortColumn),
        sortDirection,
      ),
    );
  }, [runs, searchQuery, sortColumn, sortDirection]);

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

  const openWorkflow = (workflowId: string) => {
    navigate(`/workflows/${workflowId}/edit`);
  };

  return (
    <section className="flex h-full flex-col py-4">
      <div className="max-w-md">
        <Input
          type="search"
          aria-label="Search runs"
          placeholder="Search runs..."
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
        />
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
            icon={EmptyIcon}
            title="No runs yet"
            description="Run a workflow to see execution history here."
            action={{ label: "Go to Workflows", onClick: onGoToWorkflows }}
          />
        ) : filteredRuns.length === 0 ? (
          <EmptyState
            icon={EmptyIcon}
            title="No matching runs"
            description="Try another workflow name."
          />
        ) : (
          <div className="overflow-hidden rounded-lg border border-border-default bg-surface-secondary">
            <Table>
              <TableHeader>
                <TableRow className="bg-surface-primary hover:bg-surface-primary">
                  {RUN_COLUMNS.map((column) => (
                    <TableHead
                      key={column.key}
                      aria-sort={getAriaSort(column.key)}
                      onClick={() => handleSort(column.key)}
                    >
                      {column.label}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredRuns.map((run) => (
                  <TableRow
                    key={run.id}
                    className="cursor-pointer"
                    tabIndex={0}
                    onClick={() => openWorkflow(run.workflow_id)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        openWorkflow(run.workflow_id);
                      }
                    }}
                  >
                    <TableCell>
                      <Badge variant={getRunStatusVariant(run.status)}>
                        <BadgeDot />
                        {run.status}
                      </Badge>
                    </TableCell>
                    <TableCell>{run.workflow_name}</TableCell>
                    <TableCell data-type="data">{formatRunNumber(run.run_number)}</TableCell>
                    <TableCell data-type="id">
                      {formatCommit(run.commit_sha) ? (
                        <span
                          aria-label={formatCommit(run.commit_sha) ?? undefined}
                          className="before:content-[attr(data-commit)]"
                          data-commit={formatCommit(run.commit_sha) ?? ""}
                          title={formatCommit(run.commit_sha) ?? undefined}
                        />
                      ) : (
                        <span className="italic text-muted">uncommitted</span>
                      )}
                    </TableCell>
                    <TableCell data-type="metric">{formatDuration(run.duration_seconds)}</TableCell>
                    <TableCell data-type="metric">{formatCost(run.total_cost_usd)}</TableCell>
                    <TableCell data-type="metric">
                      <EvalCell evalPassPct={run.eval_pass_pct} />
                    </TableCell>
                    <TableCell data-type="timestamp">{formatStartedAt(run.started_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </section>
  );
}

export { Component as RunsTab };
