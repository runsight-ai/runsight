import { useState, useEffect } from "react";
import { useCreateTask, useUpdateTask } from "@/queries/tasks";
import { Button } from "@runsight/ui/button";
import { Input } from "@runsight/ui/input";
import { Textarea } from "@runsight/ui/textarea";
import { Label } from "@runsight/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@runsight/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@runsight/ui/select";
import { Plus, Pencil } from "lucide-react";
import type { TaskResponse } from "@runsight/shared/zod";

const TASK_TYPES = [
  { value: "task", label: "Task" },
  { value: "python", label: "Python" },
  { value: "javascript", label: "JavaScript" },
  { value: "shell", label: "Shell" },
  { value: "http", label: "HTTP" },
  { value: "prompt", label: "Prompt" },
];

interface NewTaskModalProps {
  open: boolean;
  onClose: () => void;
}

export function NewTaskModal({ open, onClose }: NewTaskModalProps) {
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
      await createTask.mutateAsync({ name: name.trim(), type, description: description.trim() || null });
      onClose();
    } catch (error) {
      console.error("Failed to create task:", error);
      setIsSubmitting(false);
    }
  };

  const handleCancel = () => { if (!isSubmitting) onClose(); };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && handleCancel()}>
      <DialogContent className="w-[560px] max-w-[560px] p-0 gap-0 bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-xl overflow-hidden">
        <DialogHeader className="h-14 px-4 border-b border-[var(--border-default)] flex flex-row items-center justify-between shrink-0">
          <DialogTitle className="text-base font-medium text-primary tracking-tight">New Task</DialogTitle>
        </DialogHeader>
        <div className="p-4 space-y-4">
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Name <span className="text-[var(--danger-9)]">*</span></Label>
            <Input type="text" placeholder="Enter task name..." value={name} onChange={(e) => setName(e.target.value)} className="h-9 bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-md text-sm text-primary placeholder:text-[var(--text-muted)] focus:border-[var(--interactive-default)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0" disabled={isSubmitting} />
            <p className="text-xs text-[var(--text-muted)]">A unique name to identify this task</p>
          </div>
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Type</Label>
            <Select value={type} onValueChange={(value) => setType(value || "task")} disabled={isSubmitting}>
              <SelectTrigger className="h-9 bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-md text-sm text-primary focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0 focus:border-[var(--interactive-default)]">
                <SelectValue placeholder="Select a type" />
              </SelectTrigger>
              <SelectContent className="bg-[var(--surface-raised)] border-[var(--border-default)] rounded-md">
                {TASK_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value} className="text-sm text-primary focus:bg-[var(--border-default)] focus:text-primary cursor-pointer">{t.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Description <span className="text-[var(--text-muted)] font-normal">(optional)</span></Label>
            <Textarea placeholder="Describe what this task does..." value={description} onChange={(e) => setDescription(e.target.value)} className="min-h-[80px] bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-md text-sm text-primary placeholder:text-[var(--text-muted)] resize-vertical focus:border-[var(--interactive-default)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0" disabled={isSubmitting} />
          </div>
        </div>
        <DialogFooter className="h-16 px-4 border-t border-[var(--border-default)] flex items-center justify-end gap-2 shrink-0">
          <Button variant="secondary" onClick={handleCancel} disabled={isSubmitting} className="h-9 px-4 border-[var(--border-default)] bg-transparent hover:bg-[var(--surface-raised)] text-primary">Cancel</Button>
          <Button onClick={handleSubmit} disabled={!isNameFilled || isSubmitting} className="h-9 px-4 bg-[var(--interactive-default)] hover:bg-[var(--interactive-hover)] text-on-accent disabled:opacity-40">
            {isSubmitting ? (<><div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin mr-2" />Creating...</>) : (<><Plus className="w-4 h-4 mr-2" />Create Task</>)}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface EditTaskModalProps {
  item: TaskResponse | null;
  open: boolean;
  onClose: () => void;
}

export function EditTaskModal({ item: task, open, onClose }: EditTaskModalProps) {
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
      await updateTask.mutateAsync({ id: task.id, data: { name: name.trim() || null, type: type || null, description: description.trim() || null } });
      onClose();
    } catch (error) {
      console.error("Failed to update task:", error);
      setIsSubmitting(false);
    }
  };

  const handleCancel = () => { if (!isSubmitting) onClose(); };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && handleCancel()}>
      <DialogContent className="w-[560px] max-w-[560px] p-0 gap-0 bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-xl overflow-hidden">
        <DialogHeader className="h-14 px-4 border-b border-[var(--border-default)] flex flex-row items-center justify-between shrink-0">
          <DialogTitle className="text-base font-medium text-primary tracking-tight">Edit Task</DialogTitle>
        </DialogHeader>
        <div className="p-4 space-y-4">
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Name</Label>
            <Input type="text" placeholder="Enter task name..." value={name} onChange={(e) => setName(e.target.value)} className="h-9 bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-md text-sm text-primary placeholder:text-[var(--text-muted)] focus:border-[var(--interactive-default)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0" disabled={isSubmitting} />
          </div>
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Type</Label>
            <Select value={type} onValueChange={(value) => setType(value || "task")} disabled={isSubmitting}>
              <SelectTrigger className="h-9 bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-md text-sm text-primary focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0 focus:border-[var(--interactive-default)]"><SelectValue placeholder="Select a type" /></SelectTrigger>
              <SelectContent className="bg-[var(--surface-raised)] border-[var(--border-default)] rounded-md">
                {TASK_TYPES.map((t) => (<SelectItem key={t.value} value={t.value} className="text-sm text-primary focus:bg-[var(--border-default)] focus:text-primary cursor-pointer">{t.label}</SelectItem>))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Description</Label>
            <Textarea placeholder="Describe what this task does..." value={description} onChange={(e) => setDescription(e.target.value)} className="min-h-[80px] bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-md text-sm text-primary placeholder:text-[var(--text-muted)] resize-vertical focus:border-[var(--interactive-default)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0" disabled={isSubmitting} />
          </div>
        </div>
        <DialogFooter className="h-16 px-4 border-t border-[var(--border-default)] flex items-center justify-end gap-2 shrink-0">
          <Button variant="secondary" onClick={handleCancel} disabled={isSubmitting} className="h-9 px-4 border-[var(--border-default)] bg-transparent hover:bg-[var(--surface-raised)] text-primary">Cancel</Button>
          <Button onClick={handleSubmit} disabled={isSubmitting} className="h-9 px-4 bg-[var(--interactive-default)] hover:bg-[var(--interactive-hover)] text-on-accent disabled:opacity-40">
            {isSubmitting ? (<><div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin mr-2" />Saving...</>) : (<><Pencil className="w-4 h-4 mr-2" />Save Changes</>)}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
