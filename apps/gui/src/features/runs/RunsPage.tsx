import { Button } from "@runsight/ui/button";
import { useWorkflows } from "@/queries/workflows";
import { PageHeader } from "@/components/shared";
import { useSearchParams } from "react-router";
import { X } from "lucide-react";

import { RunRow } from "./RunRow";
import { RunsTab } from "./RunsTab";

function getRunsPageTitle({
  workflowFilter,
  workflowName,
  attentionOnly,
  activeOnly,
}: {
  workflowFilter: string | null;
  workflowName?: string | null;
  attentionOnly: boolean;
  activeOnly: boolean;
}) {
  if (workflowFilter) {
    return `Runs — ${workflowName ?? workflowFilter}`;
  }

  if (attentionOnly) {
    return "Runs — Attention";
  }

  if (activeOnly) {
    return "Runs — Active";
  }

  return "Runs";
}

export function Component() {
  const [searchParams, setSearchParams] = useSearchParams();
  const workflowFilter = searchParams.get("workflow");
  const attentionOnly = searchParams.get("attention") === "only";
  const activeOnly = searchParams.get("status") === "active";
  const { data: workflowsData } = useWorkflows();
  const workflowName = workflowFilter
    ? workflowsData?.items?.find((workflow) => workflow.id === workflowFilter)?.name
    : undefined;

  const clearFilters = () => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("workflow");
      next.delete("attention");
      next.delete("status");
      return next;
    });
  };

  const setWorkflowFilter = (workflowId: string | null) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (!workflowId || workflowId === "all") {
        next.delete("workflow");
      } else {
        next.set("workflow", workflowId);
      }
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

  const showClearFilters = Boolean(workflowFilter || attentionOnly || activeOnly);

  return (
    <div className="flex h-full flex-col bg-surface-primary">
      <PageHeader
        title={getRunsPageTitle({
          workflowFilter,
          workflowName: workflowName ?? undefined,
          attentionOnly,
          activeOnly,
        })}
        actions={
          showClearFilters ? (
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
          <RunsTab
            RowComponent={RunRow}
            workflowFilter={workflowFilter}
            attentionOnly={attentionOnly}
            activeOnly={activeOnly}
            onWorkflowFilterChange={setWorkflowFilter}
            onAttentionFilterChange={setAttentionFilter}
            onActiveFilterChange={setActiveFilter}
            onClearFilters={clearFilters}
          />
        </section>
      </main>
    </div>
  );
}
