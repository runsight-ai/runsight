import { useState, useMemo } from "react";
import { useNavigate } from "react-router";
import { useWorkflows, useDeleteWorkflow } from "@/queries/workflows";
import { NewWorkflowModal } from "./NewWorkflowModal";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable, type Column } from "@/components/shared/DataTable";
import { StatusBadge, type StatusVariant } from "@/components/shared/StatusBadge";
import { EmptyState } from "@runsight/ui/empty-state";
import { Button } from "@runsight/ui/button";
import { Input } from "@runsight/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@runsight/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@runsight/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@runsight/ui/dropdown-menu";
import {
  Plus,
  Upload,
  Search,
  LayoutGrid,
  List,
  MoreHorizontal,
  Trash2,
  Workflow,
  AlertCircle,
  RotateCcw,
} from "lucide-react";
import { getWorkflowIcon, getWorkflowIconBg } from "@/utils/icons";
import type { WorkflowResponse } from "@runsight/shared/zod";

type SortOption = "updated" | "name" | "created";
type ViewMode = "list" | "grid";
type StatusFilter = "all" | "active" | "draft" | "archived";

function getWorkflowStepCount(workflow: WorkflowResponse) {
  return workflow.canvas_state?.nodes?.length ?? 0;
}

function getWorkflowStatus(workflow: WorkflowResponse): {
  badgeStatus: StatusVariant;
  label: string;
  filterValue: Exclude<StatusFilter, "all" | "archived">;
} {
  if (workflow.validation_error || workflow.valid === false) {
    return {
      badgeStatus: "warning",
      label: "Needs Review",
      filterValue: "draft",
    };
  }

  if (workflow.yaml?.trim() || getWorkflowStepCount(workflow) > 0) {
    return {
      badgeStatus: "success",
      label: "Ready",
      filterValue: "active",
    };
  }

  return {
    badgeStatus: "pending",
    label: "Draft",
    filterValue: "draft",
  };
}

function getWorkflowSummary(workflow: WorkflowResponse) {
  if (workflow.validation_error) {
    return "Validation issue";
  }

  if (workflow.yaml?.trim()) {
    return "YAML workflow";
  }

  if (getWorkflowStepCount(workflow) > 0) {
    return "Canvas workflow";
  }

  return "No run data";
}

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
        if (statusFilter === "archived") {
          return false;
        }

        return getWorkflowStatus(w).filterValue === statusFilter;
      });
    }

    // Sort
    result.sort((a, b) => {
      if (sortBy === "name") {
        return (a.name || "Untitled").localeCompare(b.name || "Untitled");
      }

      const stepDifference = getWorkflowStepCount(b) - getWorkflowStepCount(a);
      if (stepDifference !== 0) {
        return stepDifference;
      }

      return (a.name || "Untitled").localeCompare(b.name || "Untitled");
    });

    return result;
  }, [workflows, searchQuery, statusFilter, sortBy]);

  const handleRowClick = (workflow: WorkflowResponse) => {
    navigate(`/workflows/${workflow.id}`);
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
              <div className="text-sm font-medium text-primary truncate">{name}</div>
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
          <div className="text-sm text-muted truncate max-w-[300px]">
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
        const count = getWorkflowStepCount(workflow);
        return (
          <div className="text-center text-sm text-muted">{count}</div>
        );
      },
    },
    {
      key: "last_run",
      header: "Last Run",
      width: "140px",
      render: (row) => {
        const workflow = row as WorkflowResponse;
        const status = getWorkflowStatus(workflow);
        return (
          <div className="flex flex-col gap-1">
            <StatusBadge status={status.badgeStatus} label={status.label} />
            <span className="text-xs text-muted">
              {getWorkflowSummary(workflow)}
            </span>
          </div>
        );
      },
    },
    {
      key: "cost",
      header: "Cost",
      width: "100px",
      render: () => {
        return (
          <div className="text-right text-sm text-muted">--</div>
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
          <div className="text-sm text-muted">
            {getWorkflowSummary(workflow)}
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
                <DropdownMenuItem 
                  onClick={(e) => { e.stopPropagation(); setWorkflowToDelete(workflow); }}
                  className="text-danger focus:text-danger"
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
      <div className="flex-1 flex flex-col bg-[var(--surface-primary)]">
        <PageHeader title="Workflows" subtitle="Loading..." />
        <div className="flex-1 p-6">
          <div className="bg-[var(--surface-secondary)] border border-[var(--border-default)] rounded-lg overflow-hidden">
            <div className="h-14 border-b border-[var(--border-default)] flex items-center px-4">
              <div className="h-4 w-32 bg-[var(--border-default)] rounded animate-pulse" />
            </div>
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-16 border-b border-[var(--border-default)] flex items-center px-4 gap-4">
                <div className="h-10 w-10 bg-[var(--border-default)] rounded-md animate-pulse" />
                <div className="flex-1">
                  <div className="h-4 w-48 bg-[var(--border-default)] rounded animate-pulse mb-2" />
                  <div className="h-3 w-32 bg-[var(--border-default)] rounded animate-pulse" />
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
      <div className="flex-1 flex flex-col bg-[var(--surface-primary)]">
        <PageHeader title="Workflows" />
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="text-center max-w-md">
            <AlertCircle className="h-12 w-12 mx-auto mb-4 text-danger" />
            <h3 className="text-lg font-medium text-primary mb-2">Failed to load workflows</h3>
            <p className="text-sm text-muted mb-4">
              {error instanceof Error ? error.message : "An error occurred while fetching workflows."}
            </p>
            <Button onClick={() => refetch()} variant="secondary">
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
      <div className="flex-1 flex flex-col bg-[var(--surface-primary)]">
        <PageHeader
          title="Workflows"
          subtitle="0 workflows"
          actions={
            <Button
              className="h-9 px-4 bg-[var(--interactive-default)] hover:bg-[var(--interactive-hover)] text-on-accent"
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
    <div className="flex-1 flex flex-col bg-[var(--surface-primary)]">
      {/* Page Header */}
      <PageHeader
        title="Workflows"
        subtitle={`${totalCount} workflow${totalCount !== 1 ? "s" : ""}`}
        actions={
          <>
            <Button
              variant="secondary"
              className="h-9 px-4 border-[var(--border-default)] bg-transparent hover:bg-[var(--surface-raised)] text-primary"
              disabled
            >
              <Upload className="w-4 h-4 mr-2" />
              Import
            </Button>
            <Button
              className="h-9 px-4 bg-[var(--interactive-default)] hover:bg-[var(--interactive-hover)] text-on-accent"
              onClick={() => setShowNewWorkflowModal(true)}
            >
              <Plus className="w-4 h-4 mr-2" />
              New Workflow
            </Button>
          </>
        }
      />

      {/* Search and Filter Bar */}
      <div className="h-14 border-b border-[var(--border-default)] flex items-center gap-3 px-4 bg-[var(--surface-secondary)]">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input
            type="text"
            placeholder="Search workflows..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Search workflows"
            className="h-9 pl-9 bg-[var(--surface-primary)] border-[var(--border-default)] rounded-md text-sm text-primary placeholder:text-[var(--text-muted)] focus:border-[var(--interactive-default)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0"
          />
        </div>

        {/* Status Filter */}
        <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as StatusFilter)}>
          <SelectTrigger aria-label="Filter by status" className="h-9 w-32 bg-[var(--surface-primary)] border-[var(--border-default)] rounded-md text-sm text-primary focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent className="bg-[var(--surface-raised)] border-[var(--border-default)] rounded-md">
            <SelectItem value="all" className="text-sm text-primary focus:bg-[var(--border-default)]">
              All
            </SelectItem>
            <SelectItem value="active" className="text-sm text-primary focus:bg-[var(--border-default)]">
              Active
            </SelectItem>
            <SelectItem value="draft" className="text-sm text-primary focus:bg-[var(--border-default)]">
              Draft
            </SelectItem>
            <SelectItem value="archived" className="text-sm text-primary focus:bg-[var(--border-default)]">
              Archived
            </SelectItem>
          </SelectContent>
        </Select>

        {/* Sort */}
        <Select value={sortBy} onValueChange={(v) => setSortBy(v as SortOption)}>
          <SelectTrigger className="h-9 w-40 bg-[var(--surface-primary)] border-[var(--border-default)] rounded-md text-sm text-primary focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0">
            <SelectValue placeholder="Sort by" />
          </SelectTrigger>
          <SelectContent className="bg-[var(--surface-raised)] border-[var(--border-default)] rounded-md">
            <SelectItem value="updated" className="text-sm text-primary focus:bg-[var(--border-default)]">
              Last updated
            </SelectItem>
            <SelectItem value="name" className="text-sm text-primary focus:bg-[var(--border-default)]">
              Name
            </SelectItem>
            <SelectItem value="created" className="text-sm text-primary focus:bg-[var(--border-default)]">
              Created
            </SelectItem>
          </SelectContent>
        </Select>

        <div className="flex-1" />

        {/* View Toggle */}
        <div className="flex items-center bg-[var(--surface-primary)] border border-[var(--border-default)] rounded-md p-0.5" role="group" aria-label="View mode">
          <Button
            variant="ghost"
            size="icon-sm"
            className={`h-7 w-7 ${viewMode === "list" ? "bg-[var(--border-default)]" : ""}`}
            onClick={() => setViewMode("list")}
            aria-label="List view"
            aria-pressed={viewMode === "list"}
          >
            <List className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            className={`h-7 w-7 ${viewMode === "grid" ? "bg-[var(--border-default)]" : ""}`}
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
            className="bg-[var(--surface-secondary)] border border-[var(--border-default)] rounded-lg overflow-hidden"
            onRowClick={(row) => handleRowClick(row as WorkflowResponse)}
          />
        ) : (
          /* Grid View */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredWorkflows.map((workflow) => {
              const name = workflow.name || "Untitled";
              const status = getWorkflowStatus(workflow);
              const stepCount = getWorkflowStepCount(workflow);

              return (
                <div
                  key={workflow.id}
                  onClick={() => handleRowClick(workflow)}
                  className="bg-[var(--surface-secondary)] border border-[var(--border-default)] rounded-lg p-4 hover:border-[var(--border-default)] hover:bg-[var(--surface-hover)] transition-all cursor-pointer group"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-md flex items-center justify-center shrink-0 ${getWorkflowIconBg(name)}`}>
                        {getWorkflowIcon(name)}
                      </div>
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-primary truncate">{name}</div>
                        <div className="text-xs text-muted">
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
                        <DropdownMenuItem
                          onClick={(e) => { e.stopPropagation(); setWorkflowToDelete(workflow); }}
                          className="text-danger focus:text-danger"
                        >
                          <Trash2 className="h-4 w-4 mr-2" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                  {workflow.description && (
                    <p className="text-xs text-muted mb-3 line-clamp-2">
                      {workflow.description}
                    </p>
                  )}
                  <div className="flex items-center justify-between pt-3 border-t border-[var(--border-default)]">
                    <StatusBadge status={status.badgeStatus} label={status.label} />
                    <span className="text-xs text-muted">
                      {getWorkflowSummary(workflow)}
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
        <DialogContent className="bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-xl">
          <DialogHeader>
            <DialogTitle className="text-base font-medium text-primary">
              Delete Workflow
            </DialogTitle>
            <DialogDescription className="text-sm text-muted">
              Are you sure you want to delete &quot;{workflowToDelete?.name || "Untitled"}&quot;? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex justify-end gap-2 mt-4">
            <Button
              variant="secondary"
              onClick={() => setWorkflowToDelete(null)}
              className="h-9 px-4 border-[var(--border-default)] bg-transparent hover:bg-[var(--surface-raised)] text-primary"
            >
              Cancel
            </Button>
            <Button
              onClick={handleDelete}
              disabled={deleteWorkflow.isPending}
              className="h-9 px-4 bg-danger hover:bg-danger/90 text-on-accent"
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
