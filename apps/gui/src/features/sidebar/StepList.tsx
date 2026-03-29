import { useSteps, useDeleteStep } from "@/queries/steps";
import { CrudListPage, type CrudListPageConfig } from "@/components/shared/CrudListPage";
import { type Column } from "@/components/shared/DataTable";
import { Badge } from "@runsight/ui/badge";
import { Footprints } from "lucide-react";
import type { StepResponse } from "@runsight/shared/zod";
import { truncateText } from "@/utils/formatting";
import { NewStepModal, EditStepModal } from "./StepModals";

function getStepTypeColor(type: string): string {
  switch (type.toLowerCase()) {
    case "python":   return "bg-success-3 text-success-9";
    case "javascript": return "bg-warning-3 text-warning-9";
    case "shell":    return "bg-[var(--surface-raised)] text-muted";
    case "http":     return "bg-info-3 text-info-9";
    case "prompt":   return "bg-accent-3 text-[var(--interactive-default)]";
    case "condition": return "bg-danger-3 text-danger-9";
    case "loop":     return "bg-accent-3 text-accent";
    default:         return "bg-neutral-3 text-muted";
  }
}

const columns: Column[] = [
  {
    key: "name",
    header: "Name",
    width: "1.5fr",
    render: (row) => {
      const step = row as StepResponse;
      return (
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-md flex items-center justify-center shrink-0 bg-[var(--accent-3)] text-[var(--interactive-default)]">
            <Footprints className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <div className="text-sm font-medium text-primary truncate">{step.name}</div>
          </div>
        </div>
      );
    },
  },
  {
    key: "type",
    header: "Type",
    width: "100px",
    render: (row) => {
      const step = row as StepResponse;
      return (
        <Badge variant="neutral" className={`${getStepTypeColor(step.type)} border-none text-xs`}>
          {step.type}
        </Badge>
      );
    },
  },
  {
    key: "path",
    header: "Path",
    width: "1.5fr",
    render: (row) => {
      const step = row as StepResponse;
      return <div className="text-sm text-muted font-mono text-xs truncate">{step.path}</div>;
    },
  },
  {
    key: "description",
    header: "Description",
    width: "2fr",
    render: (row) => {
      const step = row as StepResponse;
      return (
        <div className="text-sm text-muted truncate max-w-[300px]">
          {truncateText(step.description, 60)}
        </div>
      );
    },
  },
];

const stepConfig: CrudListPageConfig<StepResponse> = {
  resourceName: "Step",
  resourceNamePlural: "Steps",
  icon: Footprints,
  useList: useSteps,
  useDelete: useDeleteStep,
  columns,
  searchKeys: ["name", "description", "type"],
  getItemName: (step) => step.name,
  getItemId: (step) => step.id,
  CreateModal: NewStepModal,
  EditModal: EditStepModal,
  emptyTitle: "No steps found",
  emptyDescription: "Create your first step to define workflow building blocks.",
};

export function Component() {
  return <CrudListPage config={stepConfig} />;
}
