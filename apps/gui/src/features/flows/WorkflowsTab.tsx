import { DeleteConfirmDialog } from "@/components/shared/DeleteConfirmDialog";
import {
  useDeleteWorkflow,
  useSetWorkflowEnabled,
  useWorkflows,
} from "@/queries/workflows";
import { EmptyState } from "@runsight/ui/empty-state";
import { Input } from "@runsight/ui/input";
import type { WorkflowResponse } from "@runsight/shared/zod";
import { useState } from "react";
import { jsx, jsxs } from "react/jsx-runtime";
import { WorkflowRow } from "./WorkflowRow";

function EmptyIcon() {
  return null;
}

function WorkflowSkeletonRow() {
  return jsxs("li", {
    "data-testid": "workflow-skeleton-row",
    "aria-label": "Loading workflow row",
    className: "rounded-md border border-border-subtle bg-surface-secondary px-4 py-3",
    children: [
      jsx("div", {
        className: "h-4 w-40 animate-pulse rounded bg-border-default",
      }),
      jsx("div", {
        className: "mt-2 h-4 w-72 animate-pulse rounded bg-border-default",
      }),
    ],
  });
}

interface WorkflowsTabProps {
  onCreateWorkflow: () => void;
}

export function Component({ onCreateWorkflow }: WorkflowsTabProps) {
  const { data, isLoading, error, refetch } = useWorkflows();
  const deleteWorkflow = useDeleteWorkflow();
  const setWorkflowEnabled = useSetWorkflowEnabled();
  const [searchQuery, setSearchQuery] = useState("");
  const [workflowToDelete, setWorkflowToDelete] = useState<WorkflowResponse | null>(null);

  const workflows = data?.items ?? [];
  const normalizedQuery = searchQuery.trim().toLowerCase();
  const filteredWorkflows = normalizedQuery
    ? workflows.filter((workflow) =>
        (workflow.name ?? "").toLowerCase().includes(normalizedQuery),
      )
    : workflows;

  const handleConfirmDelete = async () => {
    if (!workflowToDelete) {
      return;
    }

    try {
      await deleteWorkflow.mutateAsync(workflowToDelete.id);
      setWorkflowToDelete(null);
    } catch (deleteError) {
      console.error("Failed to delete workflow:", deleteError);
    }
  };

  let content: ReturnType<typeof jsx>;

  if (isLoading) {
    content = jsx("ul", {
      className: "space-y-3",
      "aria-label": "Loading workflows",
      children: [0, 1, 2].map((index) =>
        jsx(WorkflowSkeletonRow, {}, index),
      ),
    });
  } else if (error) {
    content = jsxs("section", {
      className: "flex flex-col items-center justify-center gap-3 px-4 py-12 text-center",
      children: [
        jsx("h2", {
          dangerouslySetInnerHTML: {
            __html:
              "Couldn&#39;t load workflows. Check file permissions on custom/workflows/.",
          },
        }),
        jsx("button", {
          type: "button",
          onClick: () => refetch(),
          children: "Retry",
        }),
      ],
    });
  } else if (workflows.length === 0) {
    content = jsx(EmptyState, {
      icon: EmptyIcon,
      title: "No workflows yet",
      description: "Create your first workflow to start orchestrating AI agents.",
      action: { label: "Create Workflow", onClick: onCreateWorkflow },
    });
  } else if (filteredWorkflows.length === 0) {
    content = jsx(EmptyState, {
      icon: EmptyIcon,
      title: "No workflows match your search",
      description: `No results found for "${searchQuery}".`,
    });
  } else {
    content = jsx("ul", {
      className: "space-y-3",
      "aria-label": "Workflows",
      children: filteredWorkflows.map((workflow) =>
        jsx(
          WorkflowRow,
          {
            workflow,
            onDelete: setWorkflowToDelete,
            onToggleEnabled: (enabled: boolean) =>
              setWorkflowEnabled.mutateAsync({ id: workflow.id, enabled }),
          },
          workflow.id,
        ),
      ),
    });
  }

  return jsxs("section", {
    className: "flex h-full flex-col py-4",
    children: [
      jsx("div", {
        className: "max-w-md",
        children: jsx(Input, {
          type: "search",
          value: searchQuery,
          placeholder: "Search workflows...",
          "aria-label": "Search workflows",
          onChange: (event: { target: { value: string } }) =>
            setSearchQuery(event.target.value),
        }),
      }),
      jsx("div", {
        className: "flex-1 pt-4",
        children: content,
      }),
      jsx(DeleteConfirmDialog, {
        open: workflowToDelete !== null,
        onClose: () => setWorkflowToDelete(null),
        onConfirm: handleConfirmDelete,
        isPending: deleteWorkflow.isPending,
        resourceName: "Workflow",
        itemName: workflowToDelete?.name ?? "Untitled",
      }),
    ],
  });
}

export { Component as WorkflowsTab };
