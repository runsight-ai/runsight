import { useState, useMemo } from "react";
import { useNavigate } from "react-router";
import { useWorkflows, useDeleteWorkflow } from "@/queries/workflows";
import { NewWorkflowModal } from "./NewWorkflowModal";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable, type Column } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { CostDisplay } from "@/components/shared/CostDisplay";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Plus,
  Upload,
  Search,
  LayoutGrid,
  List,
  MoreHorizontal,
  Copy,
  Trash2,
  Workflow,
  AlertCircle,
  RotateCcw,
} from "lucide-react";
import type { WorkflowResponse } from "@/types/schemas/workflows";

// Utility functions from DashboardOrOnboarding
function getWorkflowIcon(name: string) {
  const iconClass = "w-5 h-5";
  const lower = name.toLowerCase();
  if (lower.includes("code") || lower.includes("review")) {
    return (
      <svg className={iconClass} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <rect x="2" y="3" width="20" height="6" rx="2"/>
        <rect x="2" y="15" width="20" height="6" rx="2"/>
      </svg>
    );
  }
  if (lower.includes("moderation") || lower.includes("content")) {
    return (
      <svg className={iconClass} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M12 2L2 7l10 5 10-5-10-5z"/>
        <path d="M2 17l10 5 10-5"/>
        <path d="M2 12l10 5 10-5"/>
      </svg>
    );
  }
  if (lower.includes("report") || lower.includes("daily")) {
    return (
      <svg className={iconClass} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="12" cy="12" r="10"/>
        <path d="M8 12l3 3 5-5"/>
      </svg>
    );
  }
  if (lower.includes("email") || lower.includes("classifier")) {
    return (
      <svg className={iconClass} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <rect x="3" y="4" width="18" height="18" rx="2"/>
        <line x1="16" y1="2" x2="16" y2="6"/>
        <line x1="8" y1="2" x2="8" y2="6"/>
        <line x1="3" y1="10" x2="21" y2="10"/>
      </svg>
    );
  }
  if (lower.includes("support") || lower.includes("ticket")) {
    return (
      <svg className={iconClass} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z"/>
      </svg>
    );
  }
  if (lower.includes("sync") || lower.includes("data")) {
    return (
      <svg className={iconClass} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="12" cy="12" r="10"/>
        <line x1="15" y1="9" x2="9" y2="15"/>
        <line x1="9" y1="9" x2="15" y2="15"/>
      </svg>
    );
  }
  return (
    <svg className={iconClass} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="3" y="3" width="7" height="7"/>
      <rect x="14" y="3" width="7" height="7"/>
      <rect x="14" y="14" width="7" height="7"/>
      <rect x="3" y="14" width="7" height="7"/>
    </svg>
  );
}

function getWorkflowIconBg(name: string) {
  const lower = name.toLowerCase();
  if (lower.includes("code") || lower.includes("review")) return "bg-[var(--primary-12)] text-[var(--primary)]";
  if (lower.includes("moderation") || lower.includes("content")) return "bg-[var(--warning-12)] text-[var(--warning)]";
  if (lower.includes("report") || lower.includes("daily")) return "bg-[var(--success-12)] text-[var(--success)]";
  if (lower.includes("email") || lower.includes("classifier")) return "bg-[var(--primary-12)] text-[var(--primary)]";
  if (lower.includes("support") || lower.includes("ticket")) return "bg-[var(--surface-elevated)] text-[var(--muted-foreground)]";
  if (lower.includes("sync") || lower.includes("data")) return "bg-[var(--error-12)] text-[var(--error)]";
  return "bg-[var(--primary-12)] text-[var(--primary)]";
}

function getTimeAgo(date: string | undefined): string {
  if (!date) return "—";
  const now = new Date();
  const then = new Date(date);
  const diffMs = now.getTime() - then.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);
  const diffWeeks = Math.floor(diffDays / 7);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins} min ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? "s" : ""} ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? "s" : ""} ago`;
  if (diffWeeks < 4) return `${diffWeeks} week${diffWeeks > 1 ? "s" : ""} ago`;
  return then.toLocaleDateString();
}

type SortOption = "updated" | "name" | "created";
type ViewMode = "list" | "grid";
type StatusFilter = "all" | "active" | "draft" | "archived";

export function Component() {
  const navigate = useNavigate();
  const { data: workflowsData, isLoading, error, refetch } = useWorkflows();
  const deleteWorkflow = useDeleteWorkflow();

  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [sortBy, setSortBy] = useState<SortOption>("updated");
  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [showNewWorkflowModal, setShowNewWorkflowModal] = useState(false);
  const [workflowToDelete, setWorkflowToDelete] = useState<WorkflowResponse | null>(null);

  const workflows = workflowsData?.items || [];
  const totalCount = workflowsData?.total || 0;

  // Filter and sort workflows
  const filteredWorkflows = useMemo(() => {
    let result = [...workflows];

    // Search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      result = result.filter(
        (w) =>
          (w.name || "").toLowerCase().includes(query) ||
          (w.description || "").toLowerCase().includes(query)
      );
    }

    // Status filter
    if (statusFilter !== "all") {
      result = result.filter((w) => {
        const status = w.status || "draft";
        if (statusFilter === "active") return status === "active" || status === "running";
        if (statusFilter === "draft") return status === "draft" || status === "idle";
        if (statusFilter === "archived") return status === "archived";
        return true;
      });
    }

    // Sort
    result.sort((a, b) => {
      if (sortBy === "updated") {
        const aDate = new Date(a.updated_at || a.created_at || 0).getTime();
        const bDate = new Date(b.updated_at || b.created_at || 0).getTime();
        return bDate - aDate; // Most recent first
      }
      if (sortBy === "name") {
        return (a.name || "Untitled").localeCompare(b.name || "Untitled");
      }
      if (sortBy === "created") {
        const aDate = new Date(a.created_at || 0).getTime();
        const bDate = new Date(b.created_at || 0).getTime();
        return bDate - aDate; // Most recent first
      }
      return 0;
    });

    return result;
  }, [workflows, searchQuery, statusFilter, sortBy]);

  const handleRowClick = (workflow: WorkflowResponse) => {
    navigate(`/workflows/${workflow.id}`);
  };

  const handleDuplicate = (workflow: WorkflowResponse) => {
    // TODO: Implement duplicate workflow
    console.log("Duplicate workflow:", workflow.id);
  };

  const handleDelete = async () => {
    if (!workflowToDelete) return;
    try {
      await deleteWorkflow.mutateAsync(workflowToDelete.id);
      setWorkflowToDelete(null);
    } catch (err) {
      console.error("Failed to delete workflow:", err);
    }
  };

  // Table columns definition
  const columns: Column[] = [
    {
      key: "name",
      header: "Name",
      width: "1.5fr",
      render: (row) => {
        const workflow = row as WorkflowResponse;
        const name = workflow.name || "Untitled";
        return (
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-md flex items-center justify-center shrink-0 ${getWorkflowIconBg(name)}`}>
              {getWorkflowIcon(name)}
            </div>
            <div className="min-w-0">
              <div className="text-sm font-medium text-foreground truncate">{name}</div>
            </div>
          </div>
        );
      },
    },
    {
      key: "description",
      header: "Description",
      width: "2fr",
      render: (row) => {
        const workflow = row as WorkflowResponse;
        return (
          <div className="text-sm text-muted-foreground truncate max-w-[300px]">
            {workflow.description || "—"}
          </div>
        );
      },
    },
    {
      key: "steps",
      header: "Steps",
      width: "80px",
      render: (row) => {
        const workflow = row as WorkflowResponse;
        const count = workflow.step_count ?? workflow.block_count ?? Object.keys(workflow.blocks || {}).length;
        return (
          <div className="text-center text-sm text-muted-foreground">{count || 0}</div>
        );
      },
    },
    {
      key: "last_run",
      header: "Last Run",
      width: "140px",
      render: (row) => {
        const workflow = row as WorkflowResponse;
        const status = workflow.status || "idle";
        const variant = status === "running" ? "running" : 
                       status === "completed" ? "success" : 
                       status === "failed" ? "error" : "pending";
        return (
          <div className="flex flex-col gap-1">
            <StatusBadge 
              status={variant} 
              label={status.charAt(0).toUpperCase() + status.slice(1)} 
            />
            <span className="text-xs text-muted-foreground">
              {getTimeAgo(workflow.last_run_completed_at || workflow.updated_at)}
            </span>
          </div>
        );
      },
    },
    {
      key: "cost",
      header: "Cost",
      width: "100px",
      render: (row) => {
        const workflow = row as WorkflowResponse;
        const cost = workflow.last_run_cost_usd ?? 0;
        const completedAt = workflow.last_run_completed_at;
        return (
          <div className="text-right">
            <CostDisplay cost={cost} isEstimate={!completedAt} />
          </div>
        );
      },
    },
    {
      key: "updated",
      header: "Updated",
      width: "120px",
      render: (row) => {
        const workflow = row as WorkflowResponse;
        return (
          <div className="text-sm text-muted-foreground">
            {getTimeAgo(workflow.updated_at)}
          </div>
        );
      },
    },
    {
      key: "actions",
      header: "",
      width: "48px",
      render: (row) => {
        const workflow = row as WorkflowResponse;
        return (
          <div className="flex justify-center">
            <DropdownMenu>
              <DropdownMenuTrigger>
                <Button 
                  variant="ghost" 
                  size="icon-sm" 
                  className="h-8 w-8"
                  onClick={(e) => e.stopPropagation()}
                >
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-40">
                <DropdownMenuItem onClick={(e) => { e.stopPropagation(); handleDuplicate(workflow); }}>
                  <Copy className="h-4 w-4 mr-2" />
                  Duplicate
                </DropdownMenuItem>
                <DropdownMenuItem 
                  onClick={(e) => { e.stopPropagation(); setWorkflowToDelete(workflow); }}
                  className="text-destructive focus:text-destructive"
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        );
      },
    },
  ];

  // Loading state
  if (isLoading) {
    return (
      <div className="flex-1 flex flex-col bg-[var(--background)]">
        <PageHeader title="Workflows" subtitle="Loading..." />
        <div className="flex-1 p-6">
          <div className="bg-[var(--card)] border border-[var(--border)] rounded-lg overflow-hidden">
            <div className="h-14 border-b border-[var(--border)] flex items-center px-4">
              <div className="h-4 w-32 bg-[var(--border)] rounded animate-pulse" />
            </div>
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-16 border-b border-[var(--border)] flex items-center px-4 gap-4">
                <div className="h-10 w-10 bg-[var(--border)] rounded-md animate-pulse" />
                <div className="flex-1">
                  <div className="h-4 w-48 bg-[var(--border)] rounded animate-pulse mb-2" />
                  <div className="h-3 w-32 bg-[var(--border)] rounded animate-pulse" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex-1 flex flex-col bg-[var(--background)]">
        <PageHeader title="Workflows" />
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="text-center max-w-md">
            <AlertCircle className="h-12 w-12 mx-auto mb-4 text-destructive" />
            <h3 className="text-lg font-medium text-foreground mb-2">Failed to load workflows</h3>
            <p className="text-sm text-muted-foreground mb-4">
              {error instanceof Error ? error.message : "An error occurred while fetching workflows."}
            </p>
            <Button onClick={() => refetch()} variant="outline">
              <RotateCcw className="h-4 w-4 mr-2" />
              Retry
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // Empty state - no workflows at all
  if (workflows.length === 0) {
    return (
      <div className="flex-1 flex flex-col bg-[var(--background)]">
        <PageHeader
          title="Workflows"
          subtitle="0 workflows"
          actions={
            <Button
              className="h-9 px-4 bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-white"
              onClick={() => setShowNewWorkflowModal(true)}
            >
              <Plus className="w-4 h-4 mr-2" />
              New Workflow
            </Button>
          }
        />
        <div className="flex-1 flex items-center justify-center p-8">
          <EmptyState
            icon={Workflow}
            title="No workflows yet. Create your first workflow"
            description="Workflows are visual orchestrations of AI agents. Start by creating a new workflow."
            action={{
              label: "Create Workflow",
              onClick: () => setShowNewWorkflowModal(true),
            }}
          />
        </div>
        <NewWorkflowModal
          open={showNewWorkflowModal}
          onClose={() => setShowNewWorkflowModal(false)}
        />
      </div>
    );
  }

  const hasSearchResults = filteredWorkflows.length > 0;

  return (
    <div className="flex-1 flex flex-col bg-[var(--background)]">
      {/* Page Header */}
      <PageHeader
        title="Workflows"
        subtitle={`${totalCount} workflow${totalCount !== 1 ? "s" : ""}`}
        actions={
          <>
            <Button
              variant="outline"
              className="h-9 px-4 border-[var(--input)] bg-transparent hover:bg-[var(--surface-elevated)] text-foreground"
              disabled
            >
              <Upload className="w-4 h-4 mr-2" />
              Import
            </Button>
            <Button
              className="h-9 px-4 bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-white"
              onClick={() => setShowNewWorkflowModal(true)}
            >
              <Plus className="w-4 h-4 mr-2" />
              New Workflow
            </Button>
          </>
        }
      />

      {/* Search and Filter Bar */}
      <div className="h-14 border-b border-[var(--border)] flex items-center gap-3 px-4 bg-[var(--card)]">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search workflows..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Search workflows"
            className="h-9 pl-9 bg-[var(--background)] border-[var(--border)] rounded-md text-sm text-foreground placeholder:text-[var(--muted-subtle)] focus:border-[var(--primary)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0"
          />
        </div>

        {/* Status Filter */}
        <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as StatusFilter)}>
          <SelectTrigger aria-label="Filter by status" className="h-9 w-32 bg-[var(--background)] border-[var(--border)] rounded-md text-sm text-foreground focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent className="bg-[var(--surface-elevated)] border-[var(--border)] rounded-md">
            <SelectItem value="all" className="text-sm text-foreground focus:bg-[var(--border)]">
              All
            </SelectItem>
            <SelectItem value="active" className="text-sm text-foreground focus:bg-[var(--border)]">
              Active
            </SelectItem>
            <SelectItem value="draft" className="text-sm text-foreground focus:bg-[var(--border)]">
              Draft
            </SelectItem>
            <SelectItem value="archived" className="text-sm text-foreground focus:bg-[var(--border)]">
              Archived
            </SelectItem>
          </SelectContent>
        </Select>

        {/* Sort */}
        <Select value={sortBy} onValueChange={(v) => setSortBy(v as SortOption)}>
          <SelectTrigger className="h-9 w-40 bg-[var(--background)] border-[var(--border)] rounded-md text-sm text-foreground focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0">
            <SelectValue placeholder="Sort by" />
          </SelectTrigger>
          <SelectContent className="bg-[var(--surface-elevated)] border-[var(--border)] rounded-md">
            <SelectItem value="updated" className="text-sm text-foreground focus:bg-[var(--border)]">
              Last updated
            </SelectItem>
            <SelectItem value="name" className="text-sm text-foreground focus:bg-[var(--border)]">
              Name
            </SelectItem>
            <SelectItem value="created" className="text-sm text-foreground focus:bg-[var(--border)]">
              Created
            </SelectItem>
          </SelectContent>
        </Select>

        <div className="flex-1" />

        {/* View Toggle */}
        <div className="flex items-center bg-[var(--background)] border border-[var(--border)] rounded-md p-0.5" role="group" aria-label="View mode">
          <Button
            variant="ghost"
            size="icon-sm"
            className={`h-7 w-7 ${viewMode === "list" ? "bg-[var(--border)]" : ""}`}
            onClick={() => setViewMode("list")}
            aria-label="List view"
            aria-pressed={viewMode === "list"}
          >
            <List className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            className={`h-7 w-7 ${viewMode === "grid" ? "bg-[var(--border)]" : ""}`}
            onClick={() => setViewMode("grid")}
            aria-label="Grid view"
            aria-pressed={viewMode === "grid"}
          >
            <LayoutGrid className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {!hasSearchResults ? (
          <div className="flex items-center justify-center h-full">
            <EmptyState
              icon={Search}
              title="No workflows match your search"
              description={`No results found for "${searchQuery}". Try adjusting your filters.`}
              action={{
                label: "Clear filters",
                onClick: () => {
                  setSearchQuery("");
                  setStatusFilter("all");
                },
              }}
            />
          </div>
        ) : viewMode === "list" ? (
          <DataTable
            columns={columns}
            data={filteredWorkflows.map((w) => w as Record<string, unknown>)}
            className="bg-[var(--card)] border border-[var(--border)] rounded-lg overflow-hidden"
            onRowClick={(row) => handleRowClick(row as WorkflowResponse)}
          />
        ) : (
          /* Grid View */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredWorkflows.map((workflow) => {
              const name = workflow.name || "Untitled";
              const status = workflow.status || "idle";
              const variant = status === "running" ? "running" : 
                             status === "completed" ? "success" : 
                             status === "failed" ? "error" : "pending";
              const stepCount = workflow.step_count ?? workflow.block_count ?? Object.keys(workflow.blocks || {}).length;

              return (
                <div
                  key={workflow.id}
                  onClick={() => handleRowClick(workflow)}
                  className="bg-[var(--card)] border border-[var(--border)] rounded-lg p-4 hover:border-[var(--input)] hover:bg-[var(--surface-hover)] transition-all cursor-pointer group"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-md flex items-center justify-center shrink-0 ${getWorkflowIconBg(name)}`}>
                        {getWorkflowIcon(name)}
                      </div>
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-foreground truncate">{name}</div>
                        <div className="text-xs text-muted-foreground">
                          {stepCount} {stepCount === 1 ? "step" : "steps"}
                        </div>
                      </div>
                    </div>
                    <DropdownMenu>
                      <DropdownMenuTrigger>
                        <Button 
                          variant="ghost" 
                          size="icon-sm" 
                          className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-40">
                        <DropdownMenuItem onClick={(e) => { e.stopPropagation(); handleDuplicate(workflow); }}>
                          <Copy className="h-4 w-4 mr-2" />
                          Duplicate
                        </DropdownMenuItem>
                        <DropdownMenuItem 
                          onClick={(e) => { e.stopPropagation(); setWorkflowToDelete(workflow); }}
                          className="text-destructive focus:text-destructive"
                        >
                          <Trash2 className="h-4 w-4 mr-2" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                  {workflow.description && (
                    <p className="text-xs text-muted-foreground mb-3 line-clamp-2">
                      {workflow.description}
                    </p>
                  )}
                  <div className="flex items-center justify-between pt-3 border-t border-[var(--border)]">
                    <StatusBadge status={variant} label={status.charAt(0).toUpperCase() + status.slice(1)} />
                    <span className="text-xs text-muted-foreground">
                      {getTimeAgo(workflow.updated_at)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!workflowToDelete} onOpenChange={() => setWorkflowToDelete(null)}>
        <DialogContent className="bg-[var(--card)] border-[var(--border)] rounded-xl">
          <DialogHeader>
            <DialogTitle className="text-base font-medium text-foreground">
              Delete Workflow
            </DialogTitle>
            <DialogDescription className="text-sm text-muted-foreground">
              Are you sure you want to delete &quot;{workflowToDelete?.name || "Untitled"}&quot;? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex justify-end gap-2 mt-4">
            <Button
              variant="outline"
              onClick={() => setWorkflowToDelete(null)}
              className="h-9 px-4 border-[var(--input)] bg-transparent hover:bg-[var(--surface-elevated)] text-foreground"
            >
              Cancel
            </Button>
            <Button
              onClick={handleDelete}
              disabled={deleteWorkflow.isPending}
              className="h-9 px-4 bg-destructive hover:bg-destructive/90 text-white"
            >
              {deleteWorkflow.isPending ? (
                <>
                  <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin mr-2" />
                  Deleting...
                </>
              ) : (
                <>
                  <Trash2 className="h-4 w-4 mr-2" />
                  Delete
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* New Workflow Modal */}
      <NewWorkflowModal
        open={showNewWorkflowModal}
        onClose={() => setShowNewWorkflowModal(false)}
      />
    </div>
  );
}
