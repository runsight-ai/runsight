import { useSearchParams, useNavigate } from "react-router";
import { useRuns } from "@/queries/runs";
import type { RunResponse } from "@/types/schemas/runs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Workflow, Search, X, ChevronLeft, ChevronRight, Calendar } from "lucide-react";
import { cn } from "@/utils/helpers";
import { formatDuration, formatCost, formatTimestamp } from "@/utils/formatting";
import React, { useState, useMemo } from "react";

// Status badge component matching design spec
function StatusBadge({ status }: { status: string }) {
  const normalizedStatus = status.toLowerCase();

  type VariantDef = { bg: string; text: string; dot: string; animate?: boolean };

  const variants: Record<string, VariantDef> = {
    running: {
      bg: "bg-info-3",
      text: "text-running",
      dot: "bg-running",
      animate: true,
    },
    paused: {
      bg: "bg-warning/12",
      text: "text-warning",
      dot: "bg-warning",
    },
    completed: {
      bg: "bg-success/12",
      text: "text-success",
      dot: "bg-success",
    },
    success: {
      bg: "bg-success/12",
      text: "text-success",
      dot: "bg-success",
    },
    failed: {
      bg: "bg-error/12",
      text: "text-error",
      dot: "bg-error",
    },
    killed: {
      bg: "bg-error/12",
      text: "text-error",
      dot: "bg-error",
    },
    stalled: {
      bg: "bg-warning/12",
      text: "text-warning",
      dot: "bg-warning",
    },
    partial: {
      bg: "bg-warning/12",
      text: "text-warning",
      dot: "bg-warning",
    },
    pending: {
      bg: "bg-muted-foreground/12",
      text: "text-muted",
      dot: "bg-muted-foreground",
    },
  };

  const variant: VariantDef = variants[normalizedStatus] ?? (variants.pending as VariantDef);

  return (
    <Badge
      variant="outline"
      className={cn(
        "h-[22px] px-2 gap-1.5 border-0 font-medium text-xs uppercase tracking-wide",
        variant.bg,
        variant.text
      )}
    >
      <span
        className={cn(
          "w-1.5 h-1.5 rounded-full",
          variant.dot,
          variant.animate && "animate-pulse"
        )}
      />
      {status}
    </Badge>
  );
}

// Count agents from node_summary
function countAgents(nodeSummary: RunResponse["node_summary"]): string {
  if (!nodeSummary) return "—";
  const total = nodeSummary.total ?? 0;
  return total === 1 ? "1 agent" : `${total} agents`;
}

// Tab button component
function TabButton({
  active,
  children,
  onClick,
  "aria-label": ariaLabel,
}: {
  active: boolean;
  children: React.ReactNode;
  onClick: () => void;
  "aria-label"?: string;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      aria-label={ariaLabel}
      onClick={onClick}
      className={cn(
        "h-10 px-4 text-sm font-medium transition-all border-b-2 -mb-px",
        active
          ? "text-primary border-primary"
          : "text-muted border-transparent hover:text-primary"
      )}
    >
      {children}
    </button>
  );
}

// Empty state component
function EmptyState({ heading, message }: { heading: string; message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-16 h-16 rounded-full bg-surface-tertiary flex items-center justify-center mb-4">
        <Workflow className="w-8 h-8 text-muted" strokeWidth={1.5} />
      </div>
      <h3 className="text-base font-medium text-primary mb-1">{heading}</h3>
      <p className="text-sm text-muted max-w-xs">{message}</p>
    </div>
  );
}

// Table row component for Active tab
function RunTableRow({
  run,
  onClick,
}: {
  run: RunResponse;
  onClick: () => void;
}) {
  return (
    <TableRow
      onClick={onClick}
      className="cursor-pointer hover:bg-surface-tertiary/80 border-b border-border-default"
    >
      <TableCell className="py-4">
        <div className="flex items-center gap-3">
          <Workflow
            className="w-4 h-4 text-primary shrink-0"
            strokeWidth={1.5}
          />
          <div>
            <div className="text-sm font-medium text-primary">
              {run.workflow_name}
            </div>
            <div className="text-xs text-muted font-mono">
              {run.id}
            </div>
          </div>
        </div>
      </TableCell>
      <TableCell>
        <StatusBadge status={run.status} />
      </TableCell>
      <TableCell className="text-sm text-muted">
        {formatDuration(run.duration_seconds)}
      </TableCell>
      <TableCell className="text-sm font-mono text-muted">
        {formatCost(run.total_cost_usd)}
      </TableCell>
      <TableCell className="text-sm text-muted">
        {countAgents(run.node_summary)}
      </TableCell>
    </TableRow>
  );
}

// History table row component with Completed At column
function HistoryTableRow({
  run,
  onClick,
}: {
  run: RunResponse;
  onClick: () => void;
}) {
  return (
    <TableRow
      onClick={onClick}
      className="cursor-pointer hover:bg-surface-tertiary/80 border-b border-border-default"
    >
      <TableCell className="py-4">
        <div className="flex items-center gap-3">
          <Workflow
            className="w-4 h-4 text-primary shrink-0"
            strokeWidth={1.5}
          />
          <div>
            <div className="text-sm font-medium text-primary">
              {run.workflow_name}
            </div>
            <div className="text-xs text-muted font-mono">
              {run.id}
            </div>
          </div>
        </div>
      </TableCell>
      <TableCell>
        <StatusBadge status={run.status} />
      </TableCell>
      <TableCell className="text-sm text-muted">
        {formatDuration(run.duration_seconds)}
      </TableCell>
      <TableCell className="text-sm font-mono text-muted">
        {formatCost(run.total_cost_usd)}
      </TableCell>
      <TableCell className="text-sm text-muted">
        {formatTimestamp(run.completed_at)}
      </TableCell>
    </TableRow>
  );
}

// Filter bar component for History tab
type FilterState = {
  status: string;
  dateFrom: string;
  dateTo: string;
  workflow: string;
  search: string;
};

function HistoryFilterBar({
  filters,
  onFiltersChange,
  workflowOptions,
}: {
  filters: FilterState;
  onFiltersChange: (filters: FilterState) => void;
  workflowOptions: string[];
}) {
  const handleStatusChange = (value: string | null) => {
    if (value) onFiltersChange({ ...filters, status: value });
  };

  const handleWorkflowChange = (value: string | null) => {
    if (value) onFiltersChange({ ...filters, workflow: value });
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onFiltersChange({ ...filters, search: e.target.value });
  };

  const handleDateFromChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onFiltersChange({ ...filters, dateFrom: e.target.value });
  };

  const handleDateToChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onFiltersChange({ ...filters, dateTo: e.target.value });
  };

  const clearFilters = () => {
    onFiltersChange({
      status: "all",
      dateFrom: "",
      dateTo: "",
      workflow: "all",
      search: "",
    });
  };

  const hasActiveFilters =
    filters.status !== "all" ||
    filters.workflow !== "all" ||
    filters.search ||
    filters.dateFrom ||
    filters.dateTo;

  return (
    <div className="flex items-center gap-3 px-4 py-3 bg-surface-secondary border-b border-border-default min-h-[48px] flex-wrap">
      {/* Status filter */}
      <Select value={filters.status} onValueChange={handleStatusChange}>
        <SelectTrigger className="w-[140px] h-8 text-sm">
          <SelectValue placeholder="Status" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Status</SelectItem>
          <SelectItem value="completed">Success</SelectItem>
          <SelectItem value="failed">Failed</SelectItem>
          <SelectItem value="partial">Partial</SelectItem>
        </SelectContent>
      </Select>

      {/* Workflow filter */}
      <Select value={filters.workflow} onValueChange={handleWorkflowChange}>
        <SelectTrigger className="w-[160px] h-8 text-sm">
          <SelectValue placeholder="Workflow" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Workflows</SelectItem>
          {workflowOptions.map((wf) => (
            <SelectItem key={wf} value={wf}>
              {wf}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Date range filter */}
      <div className="flex items-center gap-2">
        <div className="relative">
          <Calendar className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted" />
          <Input
            type="date"
            placeholder="From"
            value={filters.dateFrom}
            onChange={handleDateFromChange}
            className="h-8 w-[140px] pl-7 text-sm"
          />
        </div>
        <span className="text-muted text-sm">to</span>
        <div className="relative">
          <Calendar className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted" />
          <Input
            type="date"
            placeholder="To"
            value={filters.dateTo}
            onChange={handleDateToChange}
            className="h-8 w-[140px] pl-7 text-sm"
          />
        </div>
      </div>

      {/* Search input */}
      <div className="relative flex-1 min-w-[200px] max-w-xs">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
        <Input
          type="text"
          placeholder="Search runs..."
          value={filters.search}
          onChange={handleSearchChange}
          className="h-8 pl-9 text-sm"
        />
        {filters.search && (
          <button
            type="button"
            onClick={() => onFiltersChange({ ...filters, search: "" })}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-primary"
            aria-label="Clear search"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      <div className="flex-1" />

      {/* Clear filters button */}
      {hasActiveFilters && (
        <Button
          variant="ghost"
          size="sm"
          onClick={clearFilters}
          className="h-8 text-xs"
        >
          <X className="w-3.5 h-3.5 mr-1" />
          Clear filters
        </Button>
      )}
    </div>
  );
}

// Pagination component
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
  const startItem = (currentPage - 1) * pageSize + 1;
  const endItem = Math.min(currentPage * pageSize, totalItems);

  const getPageNumbers = () => {
    const pages: (number | string)[] = [];
    const maxVisible = 5;

    if (totalPages <= maxVisible) {
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      if (currentPage <= 3) {
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
    }
    return pages;
  };

  return (
    <div className="flex items-center justify-between px-4 py-3 border-t border-border-default bg-surface-secondary">
      <div className="flex items-center gap-4">
        <span className="text-sm text-muted">
          Showing {startItem}–{endItem} of {totalItems} runs
        </span>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted">Show:</span>
          <Select
            value={String(pageSize)}
            onValueChange={(v) => onPageSizeChange(Number(v))}
          >
            <SelectTrigger className="w-[70px] h-7 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="10">10</SelectItem>
              <SelectItem value="25">25</SelectItem>
              <SelectItem value="50">50</SelectItem>
              <SelectItem value="100">100</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8"
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage <= 1}
          aria-label="Previous page"
        >
          <ChevronLeft className="w-4 h-4" />
        </Button>

        <div className="flex items-center gap-1">
          {getPageNumbers().map((page, idx) => (
            <React.Fragment key={idx}>
              {page === "..." ? (
                <span className="px-2 text-muted">...</span>
              ) : (
                <Button
                  variant={currentPage === page ? "default" : "outline"}
                  size="sm"
                  className="h-8 w-8 px-0 text-sm"
                  onClick={() => onPageChange(Number(page))}
                >
                  {page}
                </Button>
              )}
            </React.Fragment>
          ))}
        </div>

        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= totalPages}
          aria-label="Next page"
        >
          <ChevronRight className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
}

export function Component() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const tab = searchParams.get("tab") || "active";

  // History tab filters state
  const [filters, setFilters] = useState<FilterState>({
    status: "all",
    dateFrom: "",
    dateTo: "",
    workflow: "all",
    search: "",
  });

  // Pagination state for history tab
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  // Reset pagination when filters change
  const handleFiltersChange = (newFilters: FilterState) => {
    setFilters(newFilters);
    setCurrentPage(1);
  };

  // Fetch runs based on tab - history uses completed,failed status
  const { data, isLoading, error } = useRuns(
    tab === "active" ? { status: "active" } : { status: "completed,failed" },
    {
      refetchInterval: tab === "active" ? 5000 : false,
    }
  );

  const runs = useMemo(() => data?.items ?? [], [data?.items]);
  const totalCount = data?.total ?? 0;

  // Extract unique workflow names for filter dropdown
  const workflowOptions = useMemo(() => {
    const workflows = new Set<string>();
    runs.forEach((run) => workflows.add(run.workflow_name));
    return Array.from(workflows).sort();
  }, [runs]);

  // Filter runs for history tab
  const filteredRuns = useMemo(() => {
    if (tab !== "history") return runs;

    return runs.filter((run) => {
      // Status filter
      if (filters.status !== "all") {
        const normalizedStatus = run.status.toLowerCase();
        if (filters.status === "completed" && normalizedStatus !== "completed" && normalizedStatus !== "success") {
          return false;
        }
        if (filters.status === "failed" && normalizedStatus !== "failed") {
          return false;
        }
        if (filters.status === "partial" && normalizedStatus !== "partial") {
          return false;
        }
      }

      // Workflow filter
      if (filters.workflow !== "all" && run.workflow_name !== filters.workflow) {
        return false;
      }

      // Search filter (workflow name or run id)
      if (filters.search) {
        const searchLower = filters.search.toLowerCase();
        const matchesWorkflow = run.workflow_name.toLowerCase().includes(searchLower);
        const matchesId = run.id.toLowerCase().includes(searchLower);
        if (!matchesWorkflow && !matchesId) {
          return false;
        }
      }

      // Date range filter (simplified - filters by completed_at)
      if (filters.dateFrom && run.completed_at) {
        const fromDate = new Date(filters.dateFrom).getTime() / 1000;
        if (run.completed_at < fromDate) return false;
      }
      if (filters.dateTo && run.completed_at) {
        const toDate = new Date(filters.dateTo).getTime() / 1000 + 86400; // End of day
        if (run.completed_at > toDate) return false;
      }

      return true;
    });
  }, [runs, filters, tab]);

  // Paginated runs for history tab
  const paginatedRuns = useMemo(() => {
    if (tab !== "history") return filteredRuns;
    const start = (currentPage - 1) * pageSize;
    const end = start + pageSize;
    return filteredRuns.slice(start, end);
  }, [filteredRuns, currentPage, pageSize, tab]);

  const totalPages = Math.ceil(filteredRuns.length / pageSize);

  const handleTabChange = (newTab: string) => {
    setSearchParams({ tab: newTab });
  };

  const handleRowClick = (runId: string) => {
    navigate(`/runs/${runId}`);
  };

  const activeCount = tab === "active" ? totalCount : 0;
  const historyCount = tab === "history" ? filteredRuns.length : 0;

  // Determine empty state message for history
  const getHistoryEmptyMessage = () => {
    if (runs.length === 0) {
      return {
        heading: "No runs in history",
        message: "Completed and failed workflows will appear here.",
      };
    }
    if (filteredRuns.length === 0) {
      return {
        heading: "No runs match filters",
        message: "Try adjusting your filter criteria to see more results.",
      };
    }
    return null;
  };

  return (
    <div className="h-full flex flex-col bg-surface-primary">
      {/* Tab bar */}
      <div className="flex items-center px-4 border-b border-border-default bg-surface-secondary" role="tablist">
        <TabButton
          active={tab === "active"}
          onClick={() => handleTabChange("active")}
          aria-label="Active runs"
        >
          Active
          {activeCount > 0 && (
            <span className="ml-2 text-xs text-muted">
              ({activeCount})
            </span>
          )}
        </TabButton>
        <TabButton
          active={tab === "history"}
          onClick={() => handleTabChange("history")}
          aria-label="Run history"
        >
          History
          {historyCount > 0 && (
            <span className="ml-2 text-xs text-muted">
              ({historyCount})
            </span>
          )}
        </TabButton>
      </div>

      {/* Filter bar - only for History tab */}
      {tab === "history" && (
        <HistoryFilterBar
          filters={filters}
          onFiltersChange={handleFiltersChange}
          workflowOptions={workflowOptions}
        />
      )}

      {/* Content area */}
      <div className="flex-1 overflow-auto p-6">
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-sm text-muted">Loading runs...</div>
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-sm text-error">
              Error loading runs: {error.message}
            </div>
          </div>
        ) : tab === "active" ? (
          // Active tab content
          runs.length === 0 ? (
            <EmptyState
              heading="No active runs"
              message="There are no workflows currently running. Start a workflow to see it here."
            />
          ) : (
            <div className="rounded-lg border border-border-default overflow-hidden bg-surface-secondary">
              <Table>
                <TableHeader>
                  <TableRow className="border-b border-border-default bg-surface-tertiary/50 hover:bg-surface-tertiary/50">
                    <TableHead className="text-xs font-semibold uppercase tracking-wide text-muted py-3">
                      Workflow
                    </TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wide text-muted py-3">
                      Status
                    </TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wide text-muted py-3">
                      Duration
                    </TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wide text-muted py-3">
                      Cost
                    </TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wide text-muted py-3">
                      Agents
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {runs.map((run) => (
                    <RunTableRow
                      key={run.id}
                      run={run}
                      onClick={() => handleRowClick(run.id)}
                    />
                  ))}
                </TableBody>
              </Table>
            </div>
          )
        ) : (
          // History tab content
          (() => {
            const emptyState = getHistoryEmptyMessage();
            if (emptyState) {
              return (
                <EmptyState
                  heading={emptyState.heading}
                  message={emptyState.message}
                />
              );
            }
            return (
              <div className="flex flex-col rounded-lg border border-border-default overflow-hidden bg-surface-secondary">
                <div className="flex-1 overflow-auto">
                  <Table>
                    <TableHeader>
                      <TableRow className="border-b border-border-default bg-surface-tertiary/50 hover:bg-surface-tertiary/50">
                        <TableHead className="text-xs font-semibold uppercase tracking-wide text-muted py-3">
                          Workflow Name
                        </TableHead>
                        <TableHead className="text-xs font-semibold uppercase tracking-wide text-muted py-3">
                          Status
                        </TableHead>
                        <TableHead className="text-xs font-semibold uppercase tracking-wide text-muted py-3">
                          Duration
                        </TableHead>
                        <TableHead className="text-xs font-semibold uppercase tracking-wide text-muted py-3">
                          Total Cost
                        </TableHead>
                        <TableHead className="text-xs font-semibold uppercase tracking-wide text-muted py-3">
                          Completed At
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {paginatedRuns.map((run) => (
                        <HistoryTableRow
                          key={run.id}
                          run={run}
                          onClick={() => handleRowClick(run.id)}
                        />
                      ))}
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
            );
          })()
        )}

        {/* Footer info - only for active tab (history has pagination footer) */}
        {!isLoading && !error && tab === "active" && (
          <div className="mt-4 flex items-center justify-between text-xs text-muted">
            <span>
              {`Showing ${runs.length} active run${runs.length !== 1 ? "s" : ""}`}
            </span>
            <span>
              {"Auto-updating every 5 seconds"}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
