import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { PageHeader } from "@/components/shared";
import { useRuns } from "@/queries/runs";
import { useAttentionItems } from "@/queries/dashboard";
import type { AttentionItem, RunResponse } from "@runsight/shared/zod";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@runsight/ui/table";
import { Badge } from "@runsight/ui/badge";
import { EmptyState } from "@runsight/ui/empty-state";
import { Input } from "@runsight/ui/input";
import { Button } from "@runsight/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@runsight/ui/select";
import {
  Workflow,
  Search,
  X,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
  Activity,
} from "lucide-react";
import { cn } from "@/utils/helpers";
import { formatCost, formatDuration, formatTimestamp } from "@/utils/formatting";

type StatusFilter = "all" | "active" | "running" | "pending" | "completed" | "failed";
type RangeFilter = "24h" | "7d" | "14d" | "30d" | "all";

const RANGE_TO_SECONDS: Record<Exclude<RangeFilter, "all">, number> = {
  "24h": 24 * 3600,
  "7d": 7 * 24 * 3600,
  "14d": 14 * 24 * 3600,
  "30d": 30 * 24 * 3600,
};

function formatAttentionType(type: AttentionItem["type"]): string {
  return type.replaceAll("_", " ");
}

function formatStatusLabel(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function getStatusVariant(status: string): { bg: string; text: string; dot: string; animate?: boolean } {
  const normalizedStatus = status.toLowerCase();
  const variants = {
    running: {
      bg: "bg-info-3",
      text: "text-info-11",
      dot: "bg-info-9",
      animate: true,
    },
    pending: {
      bg: "bg-neutral-3",
      text: "text-muted",
      dot: "bg-neutral-9",
    },
    completed: {
      bg: "bg-success-3",
      text: "text-success-11",
      dot: "bg-success-9",
    },
    failed: {
      bg: "bg-danger-3",
      text: "text-danger-11",
      dot: "bg-danger-9",
    },
  } as const;

  return variants[normalizedStatus as keyof typeof variants] ?? variants.pending;
}

function StatusBadge({ status }: { status: string }) {
  const variant = getStatusVariant(status);

  return (
    <Badge
      variant="outline"
      className={cn(
        "h-[22px] gap-1.5 border-0 px-2 text-xs font-medium uppercase tracking-wide",
        variant.bg,
        variant.text,
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          variant.dot,
          variant.animate && "animate-pulse",
        )}
      />
      {formatStatusLabel(status)}
    </Badge>
  );
}

function matchesStatusFilter(status: string, filter: StatusFilter): boolean {
  if (filter === "all") return true;
  if (filter === "active") return status === "running" || status === "pending";
  return status === filter;
}

function inRange(run: RunResponse, range: RangeFilter): boolean {
  if (range === "all") return true;
  const cutoff = Date.now() / 1000 - RANGE_TO_SECONDS[range];
  return run.created_at >= cutoff;
}

type PaginationProps = {
  currentPage: number;
  totalPages: number;
  pageSize: number;
  totalItems: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
};

function Pagination({
  currentPage,
  totalPages,
  pageSize,
  totalItems,
  onPageChange,
  onPageSizeChange,
}: PaginationProps) {
  const startItem = totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const endItem = Math.min(currentPage * pageSize, totalItems);

  const getPageNumbers = () => {
    const pages: (number | string)[] = [];
    const maxVisible = 5;

    if (totalPages <= maxVisible) {
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else if (currentPage <= 3) {
      for (let i = 1; i <= 4; i++) pages.push(i);
      pages.push("...");
      pages.push(totalPages);
    } else if (currentPage >= totalPages - 2) {
      pages.push(1);
      pages.push("...");
      for (let i = totalPages - 3; i <= totalPages; i++) pages.push(i);
    } else {
      pages.push(1);
      pages.push("...");
      for (let i = currentPage - 1; i <= currentPage + 1; i++) pages.push(i);
      pages.push("...");
      pages.push(totalPages);
    }

    return pages;
  };

  return (
    <div className="flex items-center justify-between border-t border-border-default bg-surface-secondary px-4 py-3">
      <div className="flex items-center gap-4">
        <span className="text-sm text-muted">
          Showing {startItem}–{endItem} of {totalItems} runs
        </span>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted">Show:</span>
          <Select value={String(pageSize)} onValueChange={(v) => onPageSizeChange(Number(v))}>
            <SelectTrigger className="h-7 w-[70px] text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="10">10</SelectItem>
              <SelectItem value="25">25</SelectItem>
              <SelectItem value="50">50</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant="icon-only"
          size="sm"
          className="h-8 w-8"
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage <= 1}
          aria-label="Previous page"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>

        <div className="flex items-center gap-1">
          {getPageNumbers().map((page, idx) => (
            <div key={`${page}-${idx}`}>
              {page === "..." ? (
                <span className="px-2 text-muted">...</span>
              ) : (
                <Button
                  variant={currentPage === page ? "primary" : "secondary"}
                  size="sm"
                  className="h-8 w-8 px-0 text-sm"
                  onClick={() => onPageChange(Number(page))}
                >
                  {page}
                </Button>
              )}
            </div>
          ))}
        </div>

        <Button
          variant="icon-only"
          size="sm"
          className="h-8 w-8"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= totalPages}
          aria-label="Next page"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

export function Component() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const initialStatus = (searchParams.get("status") as StatusFilter | null) ?? "all";
  const initialAttentionOnly = searchParams.get("attention") === "only";
  const [statusFilter, setStatusFilter] = useState<StatusFilter>(initialStatus);
  const [workflowFilter, setWorkflowFilter] = useState("all");
  const [rangeFilter, setRangeFilter] = useState<RangeFilter>("7d");
  const [searchQuery, setSearchQuery] = useState("");
  const [attentionOnly, setAttentionOnly] = useState(initialAttentionOnly);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  const runQueryParams = useMemo(() => {
    const params = new URLSearchParams();
    params.set("limit", "100");
    return params;
  }, []);

  const { data, isLoading, error } = useRuns(runQueryParams, { refetchInterval: 5000 });
  const { data: attentionData } = useAttentionItems(100);
  const runs = useMemo(() => data?.items ?? [], [data?.items]);
  const attentionItems = attentionData?.items ?? [];

  const attentionByRunId = useMemo(() => {
    const map = new Map<string, AttentionItem[]>();
    for (const item of attentionItems) {
      const existing = map.get(item.run_id) ?? [];
      existing.push(item);
      map.set(item.run_id, existing);
    }
    return map;
  }, [attentionItems]);

  const workflowOptions = useMemo(() => {
    const workflows = new Set<string>();
    runs.forEach((run) => workflows.add(run.workflow_name));
    return Array.from(workflows).sort();
  }, [runs]);

  const filteredRuns = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return runs
      .filter((run) => matchesStatusFilter(run.status, statusFilter))
      .filter((run) => (workflowFilter === "all" ? true : run.workflow_name === workflowFilter))
      .filter((run) => inRange(run, rangeFilter))
      .filter((run) => (attentionOnly ? (attentionByRunId.get(run.id)?.length ?? 0) > 0 : true))
      .filter((run) => {
        if (!query) return true;
        return (
          run.workflow_name.toLowerCase().includes(query) ||
          run.id.toLowerCase().includes(query)
        );
      })
      .sort((a, b) => {
        const aIsActive = a.status === "running" || a.status === "pending";
        const bIsActive = b.status === "running" || b.status === "pending";
        if (aIsActive !== bIsActive) return aIsActive ? -1 : 1;

        const aAttention = attentionByRunId.get(a.id)?.length ?? 0;
        const bAttention = attentionByRunId.get(b.id)?.length ?? 0;
        if (aAttention !== bAttention) return bAttention - aAttention;

        return b.created_at - a.created_at;
      });
  }, [
    attentionByRunId,
    attentionOnly,
    rangeFilter,
    runs,
    searchQuery,
    statusFilter,
    workflowFilter,
  ]);

  const totalAttentionRuns = useMemo(() => {
    return new Set(attentionItems.map((item) => item.run_id)).size;
  }, [attentionItems]);

  const paginatedRuns = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredRuns.slice(start, start + pageSize);
  }, [currentPage, filteredRuns, pageSize]);

  const totalPages = Math.max(1, Math.ceil(filteredRuns.length / pageSize));

  const syncSearchParams = (nextStatus: StatusFilter, nextAttentionOnly: boolean) => {
    const next = new URLSearchParams(searchParams);
    if (nextStatus === "all") {
      next.delete("status");
    } else {
      next.set("status", nextStatus);
    }

    if (nextAttentionOnly) {
      next.set("attention", "only");
    } else {
      next.delete("attention");
    }
    setSearchParams(next, { replace: true });
  };

  const clearFilters = () => {
    setStatusFilter("all");
    setWorkflowFilter("all");
    setRangeFilter("7d");
    setSearchQuery("");
    setAttentionOnly(false);
    setCurrentPage(1);
    setSearchParams({}, { replace: true });
  };

  const hasActiveFilters =
    statusFilter !== "all" ||
    workflowFilter !== "all" ||
    rangeFilter !== "7d" ||
    searchQuery.trim().length > 0 ||
    attentionOnly;

  return (
    <div className="flex h-full flex-col">
      <PageHeader title="Runs" />

      <main className="flex flex-1 min-h-0 flex-col bg-surface-primary p-6">
        <div className="mb-4 grid grid-cols-1 gap-4 rounded-lg border border-border-default bg-surface-secondary p-4 xl:grid-cols-[minmax(220px,1.2fr)_180px_180px_auto_auto]">
          <div className="space-y-2">
            <label className="text-xs font-medium uppercase tracking-wide text-muted">
              Search
            </label>
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
              <Input
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setCurrentPage(1);
                }}
                placeholder="Search workflow or run id"
                className="pl-9"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery("")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-primary"
                  aria-label="Clear search"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-medium uppercase tracking-wide text-muted">
              Status
            </label>
            <Select
              value={statusFilter}
              onValueChange={(value) => {
                const nextStatus = value as StatusFilter;
                setStatusFilter(nextStatus);
                setCurrentPage(1);
                syncSearchParams(nextStatus, attentionOnly);
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="running">Running</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
                <SelectItem value="failed">Failed</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-medium uppercase tracking-wide text-muted">
              Workflow
            </label>
            <Select
              value={workflowFilter}
              onValueChange={(value) => {
                setWorkflowFilter(value ?? "all");
                setCurrentPage(1);
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All workflows</SelectItem>
                {workflowOptions.map((workflow) => (
                  <SelectItem key={workflow} value={workflow}>
                    {workflow}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-medium uppercase tracking-wide text-muted">
              Range
            </label>
            <div className="flex flex-wrap gap-2">
              {(["24h", "7d", "14d", "30d", "all"] as const).map((range) => (
                <Button
                  key={range}
                  variant={rangeFilter === range ? "primary" : "secondary"}
                  size="sm"
                  onClick={() => {
                    setRangeFilter(range);
                    setCurrentPage(1);
                  }}
                >
                  {range}
                </Button>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-end justify-between gap-3 xl:justify-end">
            <Button
              variant={attentionOnly ? "primary" : "secondary"}
              size="sm"
              onClick={() => {
                const next = !attentionOnly;
                setAttentionOnly(next);
                setCurrentPage(1);
                syncSearchParams(statusFilter, next);
              }}
            >
              <AlertTriangle className="mr-2 h-4 w-4" />
              Attention Only
              {totalAttentionRuns > 0 && (
                <span className="ml-2 rounded-full bg-warning-3 px-1.5 py-0.5 text-[10px] text-warning-11">
                  {totalAttentionRuns}
                </span>
              )}
            </Button>

            {hasActiveFilters && (
              <Button variant="ghost" size="sm" onClick={clearFilters}>
                <X className="mr-2 h-4 w-4" />
                Clear filters
              </Button>
            )}
          </div>
        </div>

        {isLoading ? (
          <div className="flex flex-1 items-center justify-center rounded-lg border border-border-default bg-surface-secondary">
            <div className="text-sm text-muted">Loading runs...</div>
          </div>
        ) : error ? (
          <div className="flex flex-1 items-center justify-center rounded-lg border border-border-default bg-surface-secondary">
            <div className="text-sm text-danger-11">Error loading runs: {error.message}</div>
          </div>
        ) : filteredRuns.length === 0 ? (
          <div className="flex flex-1 items-center justify-center rounded-lg border border-border-default bg-surface-secondary">
            <EmptyState
              icon={attentionOnly ? AlertTriangle : Workflow}
              title={attentionOnly ? "No runs need attention" : "No runs found"}
              description={
                attentionOnly
                  ? "Recent production runs with regressions, cost spikes, quality drops, or new baselines will appear here."
                  : "Try adjusting your filters to see more runs."
              }
            />
          </div>
        ) : (
          <div className="flex flex-1 min-h-0 flex-col overflow-hidden rounded-lg border border-border-default bg-surface-secondary">
            <div className="flex-1 min-h-0 overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow className="border-b border-border-default bg-surface-tertiary/50 hover:bg-surface-tertiary/50">
                    <TableHead>Workflow</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Attention</TableHead>
                    <TableHead>Duration</TableHead>
                    <TableHead>Cost</TableHead>
                    <TableHead>Completed At</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {paginatedRuns.map((run) => {
                    const runAttention = attentionByRunId.get(run.id) ?? [];
                    const primaryAttention = runAttention[0];
                    return (
                      <TableRow
                        key={run.id}
                        className="cursor-pointer border-b border-border-default hover:bg-surface-tertiary/50"
                        onClick={() => navigate(`/runs/${run.id}`)}
                      >
                        <TableCell className="py-4">
                          <div className="flex items-center gap-3">
                            <Workflow className="h-4 w-4 shrink-0 text-primary" strokeWidth={1.5} />
                            <div className="min-w-0">
                              <div className="text-sm font-medium text-primary">
                                {run.workflow_name}
                              </div>
                              <div className="font-mono text-xs text-muted">{run.id}</div>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={run.status} />
                        </TableCell>
                        <TableCell>
                          {runAttention.length > 0 ? (
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge variant={primaryAttention?.severity === "info" ? "info" : "warning"}>
                                {formatAttentionType(primaryAttention?.type ?? "assertion_regression")}
                              </Badge>
                              {runAttention.length > 1 && (
                                <span className="text-xs text-muted">+{runAttention.length - 1} more</span>
                              )}
                            </div>
                          ) : (
                            <span className="text-sm text-muted">—</span>
                          )}
                        </TableCell>
                        <TableCell className="text-sm text-muted">
                          {formatDuration(run.duration_seconds)}
                        </TableCell>
                        <TableCell className="font-mono text-sm text-muted">
                          {formatCost(run.total_cost_usd)}
                        </TableCell>
                        <TableCell className="text-sm text-muted">
                          {run.completed_at ? formatTimestamp(run.completed_at) : (
                            <div className="inline-flex items-center gap-2 text-info-11">
                              <Activity className="h-3.5 w-3.5" />
                              In progress
                            </div>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>

            <Pagination
              currentPage={currentPage}
              totalPages={totalPages}
              pageSize={pageSize}
              totalItems={filteredRuns.length}
              onPageChange={setCurrentPage}
              onPageSizeChange={(size) => {
                setPageSize(size);
                setCurrentPage(1);
              }}
            />
          </div>
        )}
      </main>
    </div>
  );
}
