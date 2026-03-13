import { useState, useMemo, useEffect } from "react";
import {
  useTasks,
  useCreateTask,
  useUpdateTask,
  useDeleteTask,
} from "@/queries/tasks";
import { PageHeader } from "@/components/shared/PageHeader";
import { DataTable, type Column } from "@/components/shared/DataTable";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Plus,
  Search,
  AlertCircle,
  RotateCcw,
  CheckSquare,
  MoreHorizontal,
  Trash2,
  Pencil,
} from "lucide-react";
import type { TaskResponse } from "@/types/schemas/tasks";

// Available task types
const TASK_TYPES = [
  { value: "task", label: "Task" },
  { value: "python", label: "Python" },
  { value: "javascript", label: "JavaScript" },
  { value: "shell", label: "Shell" },
  { value: "http", label: "HTTP" },
  { value: "prompt", label: "Prompt" },
];

function truncateText(text: string | null | undefined, maxLength: number): string {
  if (!text) return "—";
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + "...";
}

function getTaskTypeColor(type: string): string {
  switch (type.toLowerCase()) {
    case "python":
      return "bg-[rgba(40,167,69,0.12)] text-[#28A745]";
    case "javascript":
      return "bg-[rgba(245,166,35,0.12)] text-[#F5A623]";
    case "shell":
      return "bg-[#22222A] text-[#9292A0]";
    case "http":
      return "bg-[rgba(0,229,255,0.12)] text-[#00E5FF]";
    case "prompt":
      return "bg-[rgba(94,106,210,0.12)] text-[#5E6AD2]";
    default:
      return "bg-[rgba(146,146,160,0.12)] text-[#9292A0]";
  }
}

// New Task Modal Component
interface NewTaskModalProps {
  open: boolean;
  onClose: () => void;
}

function NewTaskModal({ open, onClose }: NewTaskModalProps) {
  const createTask = useCreateTask();
  const [name, setName] = useState("");
  const [type, setType] = useState("task");
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isNameFilled = name.trim().length > 0;

  useEffect(() => {
    if (!open) {
      setName("");
      setType("task");
      setDescription("");
      setIsSubmitting(false);
    }
  }, [open]);

  const handleSubmit = async () => {
    if (!isNameFilled || isSubmitting) return;

    setIsSubmitting(true);
    try {
      await createTask.mutateAsync({
        name: name.trim(),
        type,
        description: description.trim() || null,
      });
      onClose();
    } catch (error) {
      console.error("Failed to create task:", error);
      setIsSubmitting(false);
    }
  };

  const handleCancel = () => {
    if (!isSubmitting) {
      onClose();
    }
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && handleCancel()}>
      <DialogContent className="w-[560px] max-w-[560px] p-0 gap-0 bg-[#16161C] border-[#2D2D35] rounded-xl overflow-hidden">
        <DialogHeader className="h-14 px-4 border-b border-[#2D2D35] flex flex-row items-center justify-between shrink-0">
          <DialogTitle className="text-base font-medium text-foreground tracking-tight">
            New Task
          </DialogTitle>
        </DialogHeader>

        <div className="p-4 space-y-4">
          {/* Name Field */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Name <span className="text-[#E53935]">*</span>
            </Label>
            <Input
              type="text"
              placeholder="Enter task name..."
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-9 bg-[#16161C] border-[#2D2D35] rounded-md text-sm text-foreground placeholder:text-[#5E5E6B] focus:border-[#5E6AD2] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0"
              disabled={isSubmitting}
            />
            <p className="text-xs text-[#5E5E6B]">A unique name to identify this task</p>
          </div>

          {/* Type Field */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Type
            </Label>
            <Select
              value={type}
              onValueChange={(value) => setType(value || "task")}
              disabled={isSubmitting}
            >
              <SelectTrigger className="h-9 bg-[#16161C] border-[#2D2D35] rounded-md text-sm text-foreground focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0 focus:border-[#5E6AD2]">
                <SelectValue placeholder="Select a type" />
              </SelectTrigger>
              <SelectContent className="bg-[#22222A] border-[#2D2D35] rounded-md">
                {TASK_TYPES.map((t) => (
                  <SelectItem
                    key={t.value}
                    value={t.value}
                    className="text-sm text-foreground focus:bg-[#2D2D35] focus:text-foreground cursor-pointer"
                  >
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Description Field */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Description <span className="text-[#5E5E6B] font-normal">(optional)</span>
            </Label>
            <Textarea
              placeholder="Describe what this task does..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="min-h-[80px] bg-[#16161C] border-[#2D2D35] rounded-md text-sm text-foreground placeholder:text-[#5E5E6B] resize-vertical focus:border-[#5E6AD2] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0"
              disabled={isSubmitting}
            />
          </div>
        </div>

        <DialogFooter className="h-16 px-4 border-t border-[#2D2D35] flex items-center justify-end gap-2 shrink-0">
          <Button
            variant="outline"
            onClick={handleCancel}
            disabled={isSubmitting}
            className="h-9 px-4 border-[#3F3F4A] bg-transparent hover:bg-[#22222A] text-foreground"
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!isNameFilled || isSubmitting}
            className="h-9 px-4 bg-[#5E6AD2] hover:bg-[#717EE3] text-white disabled:opacity-40"
          >
            {isSubmitting ? (
              <>
                <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin mr-2" />
                Creating...
              </>
            ) : (
              <>
                <Plus className="w-4 h-4 mr-2" />
                Create Task
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// Edit Task Modal Component
interface EditTaskModalProps {
  task: TaskResponse | null;
  open: boolean;
  onClose: () => void;
}

function EditTaskModal({ task, open, onClose }: EditTaskModalProps) {
  const updateTask = useUpdateTask();
  const [name, setName] = useState("");
  const [type, setType] = useState("task");
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (task && open) {
      setName(task.name || "");
      setType(task.type || "task");
      setDescription(task.description || "");
    }
  }, [task, open]);

  const handleSubmit = async () => {
    if (!task || isSubmitting) return;

    setIsSubmitting(true);
    try {
      await updateTask.mutateAsync({
        id: task.id,
        data: {
          name: name.trim() || null,
          type: type || null,
          description: description.trim() || null,
        },
      });
      onClose();
    } catch (error) {
      console.error("Failed to update task:", error);
      setIsSubmitting(false);
    }
  };

  const handleCancel = () => {
    if (!isSubmitting) {
      onClose();
    }
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && handleCancel()}>
      <DialogContent className="w-[560px] max-w-[560px] p-0 gap-0 bg-[#16161C] border-[#2D2D35] rounded-xl overflow-hidden">
        <DialogHeader className="h-14 px-4 border-b border-[#2D2D35] flex flex-row items-center justify-between shrink-0">
          <DialogTitle className="text-base font-medium text-foreground tracking-tight">
            Edit Task
          </DialogTitle>
        </DialogHeader>

        <div className="p-4 space-y-4">
          {/* Name Field */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Name
            </Label>
            <Input
              type="text"
              placeholder="Enter task name..."
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-9 bg-[#16161C] border-[#2D2D35] rounded-md text-sm text-foreground placeholder:text-[#5E5E6B] focus:border-[#5E6AD2] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0"
              disabled={isSubmitting}
            />
          </div>

          {/* Type Field */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Type
            </Label>
            <Select
              value={type}
              onValueChange={(value) => setType(value || "task")}
              disabled={isSubmitting}
            >
              <SelectTrigger className="h-9 bg-[#16161C] border-[#2D2D35] rounded-md text-sm text-foreground focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0 focus:border-[#5E6AD2]">
                <SelectValue placeholder="Select a type" />
              </SelectTrigger>
              <SelectContent className="bg-[#22222A] border-[#2D2D35] rounded-md">
                {TASK_TYPES.map((t) => (
                  <SelectItem
                    key={t.value}
                    value={t.value}
                    className="text-sm text-foreground focus:bg-[#2D2D35] focus:text-foreground cursor-pointer"
                  >
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Description Field */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Description
            </Label>
            <Textarea
              placeholder="Describe what this task does..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="min-h-[80px] bg-[#16161C] border-[#2D2D35] rounded-md text-sm text-foreground placeholder:text-[#5E5E6B] resize-vertical focus:border-[#5E6AD2] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0"
              disabled={isSubmitting}
            />
          </div>
        </div>

        <DialogFooter className="h-16 px-4 border-t border-[#2D2D35] flex items-center justify-end gap-2 shrink-0">
          <Button
            variant="outline"
            onClick={handleCancel}
            disabled={isSubmitting}
            className="h-9 px-4 border-[#3F3F4A] bg-transparent hover:bg-[#22222A] text-foreground"
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="h-9 px-4 bg-[#5E6AD2] hover:bg-[#717EE3] text-white disabled:opacity-40"
          >
            {isSubmitting ? (
              <>
                <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin mr-2" />
                Saving...
              </>
            ) : (
              <>
                <Pencil className="w-4 h-4 mr-2" />
                Save Changes
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function Component() {
  const { data: tasksData, isLoading, error, refetch } = useTasks();
  const deleteTask = useDeleteTask();

  const [searchQuery, setSearchQuery] = useState("");
  const [showNewTaskModal, setShowNewTaskModal] = useState(false);
  const [taskToEdit, setTaskToEdit] = useState<TaskResponse | null>(null);
  const [taskToDelete, setTaskToDelete] = useState<TaskResponse | null>(null);

  const tasks = tasksData?.items || [];
  const totalCount = tasksData?.total || 0;

  // Filter tasks by search
  const filteredTasks = useMemo(() => {
    if (!searchQuery.trim()) return tasks;
    const query = searchQuery.toLowerCase();
    return tasks.filter(
      (t) =>
        t.name.toLowerCase().includes(query) ||
        (t.description || "").toLowerCase().includes(query) ||
        t.type.toLowerCase().includes(query)
    );
  }, [tasks, searchQuery]);

  const handleDelete = async () => {
    if (!taskToDelete) return;
    try {
      await deleteTask.mutateAsync(taskToDelete.id);
      setTaskToDelete(null);
    } catch (err) {
      console.error("Failed to delete task:", err);
    }
  };

  // Table columns definition
  const columns: Column[] = [
    {
      key: "name",
      header: "Name",
      width: "1.5fr",
      render: (row) => {
        const task = row as TaskResponse;
        return (
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-md flex items-center justify-center shrink-0 bg-[rgba(94,106,210,0.12)] text-[#5E6AD2]">
              <CheckSquare className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <div className="text-sm font-medium text-foreground truncate">{task.name}</div>
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
          <Badge
            variant="secondary"
            className={`${getTaskTypeColor(task.type)} border-none text-xs`}
          >
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
        return (
          <div className="text-sm text-muted-foreground font-mono text-xs truncate">
            {task.path}
          </div>
        );
      },
    },
    {
      key: "description",
      header: "Description",
      width: "2fr",
      render: (row) => {
        const task = row as TaskResponse;
        return (
          <div className="text-sm text-muted-foreground truncate max-w-[300px]">
            {truncateText(task.description, 60)}
          </div>
        );
      },
    },
    {
      key: "actions",
      header: "",
      width: "48px",
      render: (row) => {
        const task = row as TaskResponse;
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
                  onClick={(e) => {
                    e.stopPropagation();
                    setTaskToEdit(task);
                  }}
                >
                  <Pencil className="h-4 w-4 mr-2" />
                  Edit
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={(e) => {
                    e.stopPropagation();
                    setTaskToDelete(task);
                  }}
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
      <div className="flex-1 flex flex-col bg-[#0D0D12]">
        <PageHeader title="Tasks" subtitle="Loading..." />
        <div className="flex-1 p-6">
          <div className="bg-[#16161C] border border-[#2D2D35] rounded-lg overflow-hidden">
            <div className="h-14 border-b border-[#2D2D35] flex items-center px-4">
              <div className="h-4 w-32 bg-[#2D2D35] rounded animate-pulse" />
            </div>
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-16 border-b border-[#2D2D35] flex items-center px-4 gap-4">
                <div className="h-10 w-10 bg-[#2D2D35] rounded-md animate-pulse" />
                <div className="flex-1">
                  <div className="h-4 w-48 bg-[#2D2D35] rounded animate-pulse mb-2" />
                  <div className="h-3 w-32 bg-[#2D2D35] rounded animate-pulse" />
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
      <div className="flex-1 flex flex-col bg-[#0D0D12]">
        <PageHeader title="Tasks" />
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="text-center max-w-md">
            <AlertCircle className="h-12 w-12 mx-auto mb-4 text-destructive" />
            <h3 className="text-lg font-medium text-foreground mb-2">Failed to load tasks</h3>
            <p className="text-sm text-muted-foreground mb-4">
              {error instanceof Error ? error.message : "An error occurred while fetching tasks."}
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

  // Empty state - no tasks at all
  if (tasks.length === 0) {
    return (
      <div className="flex-1 flex flex-col bg-[#0D0D12]">
        <PageHeader
          title="Tasks"
          subtitle="0 tasks"
          actions={
            <Button
              className="h-9 px-4 bg-[#5E6AD2] hover:bg-[#717EE3] text-white"
              onClick={() => setShowNewTaskModal(true)}
            >
              <Plus className="w-4 h-4 mr-2" />
              New Task
            </Button>
          }
        />
        <div className="flex-1 flex items-center justify-center p-8">
          <EmptyState
            icon={CheckSquare}
            title="No tasks found"
            description="Create your first task to define reusable operations."
            action={{
              label: "Create Task",
              onClick: () => setShowNewTaskModal(true),
            }}
          />
        </div>
        <NewTaskModal open={showNewTaskModal} onClose={() => setShowNewTaskModal(false)} />
      </div>
    );
  }

  const hasSearchResults = filteredTasks.length > 0;

  return (
    <div className="flex-1 flex flex-col bg-[#0D0D12]">
      {/* Page Header */}
      <PageHeader
        title="Tasks"
        subtitle={`${totalCount} task${totalCount !== 1 ? "s" : ""}`}
        actions={
          <Button
            className="h-9 px-4 bg-[#5E6AD2] hover:bg-[#717EE3] text-white"
            onClick={() => setShowNewTaskModal(true)}
          >
            <Plus className="w-4 h-4 mr-2" />
            New Task
          </Button>
        }
      />

      {/* Search Bar */}
      <div className="h-14 border-b border-[#2D2D35] flex items-center gap-3 px-4 bg-[#16161C]">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search tasks..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Search tasks"
            className="h-9 pl-9 bg-[#0D0D12] border-[#2D2D35] rounded-md text-sm text-foreground placeholder:text-[#5E5E6B] focus:border-[#5E6AD2] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0"
          />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {!hasSearchResults ? (
          <div className="flex items-center justify-center h-full">
            <EmptyState
              icon={Search}
              title="No tasks match your search"
              description={`No results found for "${searchQuery}". Try adjusting your search.`}
              action={{
                label: "Clear search",
                onClick: () => setSearchQuery(""),
              }}
            />
          </div>
        ) : (
          <DataTable
            columns={columns}
            data={filteredTasks.map((t) => t as Record<string, unknown>)}
            className="bg-[#16161C] border border-[#2D2D35] rounded-lg overflow-hidden"
            onRowClick={(row) => setTaskToEdit(row as TaskResponse)}
          />
        )}
      </div>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!taskToDelete} onOpenChange={() => setTaskToDelete(null)}>
        <DialogContent className="bg-[#16161C] border-[#2D2D35] rounded-xl">
          <DialogHeader>
            <DialogTitle className="text-base font-medium text-foreground">
              Delete Task
            </DialogTitle>
            <DialogDescription className="text-sm text-muted-foreground">
              Are you sure you want to delete &quot;{taskToDelete?.name || "Unnamed Task"}&quot;?
              This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex justify-end gap-2 mt-4">
            <Button
              variant="outline"
              onClick={() => setTaskToDelete(null)}
              className="h-9 px-4 border-[#3F3F4A] bg-transparent hover:bg-[#22222A] text-foreground"
            >
              Cancel
            </Button>
            <Button
              onClick={handleDelete}
              disabled={deleteTask.isPending}
              className="h-9 px-4 bg-destructive hover:bg-destructive/90 text-white"
            >
              {deleteTask.isPending ? (
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

      {/* New Task Modal */}
      <NewTaskModal open={showNewTaskModal} onClose={() => setShowNewTaskModal(false)} />

      {/* Edit Task Modal */}
      <EditTaskModal
        task={taskToEdit}
        open={!!taskToEdit}
        onClose={() => setTaskToEdit(null)}
      />
    </div>
  );
}
