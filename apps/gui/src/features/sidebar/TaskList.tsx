import { useTasks, useCreateTask, useUpdateTask, useDeleteTask } from "@/queries/tasks";
import { CrudListPage, type CrudListPageConfig } from "@/components/shared/CrudListPage";
import { type Column } from "@/components/shared/DataTable";
import { Badge } from "@runsight/ui/badge";
import { CheckSquare } from "lucide-react";
import type { TaskResponse } from "@runsight/shared/zod";
import { truncateText } from "@/utils/formatting";
import { NewTaskModal, EditTaskModal } from "./TaskModals";

function getTaskTypeColor(type: string): string {
  switch (type.toLowerCase()) {
    case "python": return "bg-success-3 text-[var(--success-9)]";
    case "javascript": return "bg-warning-3 text-[var(--warning-9)]";
    case "shell": return "bg-[var(--surface-raised)] text-[var(--text-muted)]";
    case "http": return "bg-[var(--info-3)] text-[var(--info-9)]";
    case "prompt": return "bg-[var(--accent-3)] text-[var(--interactive-default)]";
    default: return "bg-[var(--neutral-3)] text-[var(--text-muted)]";
  }
}

const columns: Column[] = [
  {
    key: "name",
    header: "Name",
    width: "1.5fr",
    render: (row) => {
      const task = row as TaskResponse;
      return (
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-md flex items-center justify-center shrink-0 bg-[var(--accent-3)] text-[var(--interactive-default)]">
            <CheckSquare className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <div className="text-sm font-medium text-primary truncate">{task.name}</div>
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
      const task = row as TaskResponse;
      return (
        <Badge variant="neutral" className={`${getTaskTypeColor(task.type)} border-none text-xs`}>
          {task.type}
        </Badge>
      );
    },
  },
  {
    key: "path",
    header: "Path",
    width: "1.5fr",
    render: (row) => {
      const task = row as TaskResponse;
      return <div className="text-sm text-muted font-mono text-xs truncate">{task.path}</div>;
    },
  },
  {
    key: "description",
    header: "Description",
    width: "2fr",
    render: (row) => {
      const task = row as TaskResponse;
      return (
        <div className="text-sm text-muted truncate max-w-[300px]">
          {truncateText(task.description, 60)}
        </div>
      );
    },
  },
];

const taskConfig: CrudListPageConfig<TaskResponse> = {
  resourceName: "Task",
  resourceNamePlural: "Tasks",
  icon: CheckSquare,
  useList: useTasks,
  useCreate: useCreateTask,
  useUpdate: useUpdateTask,
  useDelete: useDeleteTask,
  columns,
  searchKeys: ["name", "description", "type"],
  getItemName: (task) => task.name,
  getItemId: (task) => task.id,
  CreateModal: NewTaskModal,
  EditModal: EditTaskModal,
  emptyTitle: "No tasks found",
  emptyDescription: "Create your first task to define reusable operations.",
};

export function Component() {
  return <CrudListPage config={taskConfig} />;
}
