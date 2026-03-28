import { useState, useEffect } from "react";
import { useCreateStep, useUpdateStep } from "@/queries/steps";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Plus, Pencil } from "lucide-react";
import type { StepResponse } from "@/types/generated/zod";

const STEP_TYPES = [
  { value: "step", label: "Step" },
  { value: "python", label: "Python" },
  { value: "javascript", label: "JavaScript" },
  { value: "shell", label: "Shell" },
  { value: "http", label: "HTTP" },
  { value: "prompt", label: "Prompt" },
  { value: "condition", label: "Condition" },
  { value: "loop", label: "Loop" },
];

interface NewStepModalProps {
  open: boolean;
  onClose: () => void;
}

export function NewStepModal({ open, onClose }: NewStepModalProps) {
  const createStep = useCreateStep();
  const [name, setName] = useState("");
  const [type, setType] = useState("step");
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isNameFilled = name.trim().length > 0;

  useEffect(() => {
    if (!open) {
      setName("");
      setType("step");
      setDescription("");
      setIsSubmitting(false);
    }
  }, [open]);

  const handleSubmit = async () => {
    if (!isNameFilled || isSubmitting) return;
    setIsSubmitting(true);
    try {
      await createStep.mutateAsync({ name: name.trim(), type, description: description.trim() || null });
      onClose();
    } catch (error) {
      console.error("Failed to create step:", error);
      setIsSubmitting(false);
    }
  };

  const handleCancel = () => { if (!isSubmitting) onClose(); };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && handleCancel()}>
      <DialogContent className="w-[560px] max-w-[560px] p-0 gap-0 bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-xl overflow-hidden">
        <DialogHeader className="h-14 px-4 border-b border-[var(--border-default)] flex flex-row items-center justify-between shrink-0">
          <DialogTitle className="text-base font-medium text-primary tracking-tight">New Step</DialogTitle>
        </DialogHeader>
        <div className="p-4 space-y-4">
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Name <span className="text-[var(--danger-9)]">*</span></Label>
            <Input type="text" placeholder="Enter step name..." value={name} onChange={(e) => setName(e.target.value)} className="h-9 bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-md text-sm text-primary placeholder:text-[var(--text-muted)] focus:border-[var(--interactive-default)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0" disabled={isSubmitting} />
            <p className="text-xs text-[var(--text-muted)]">A unique name to identify this step</p>
          </div>
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Type</Label>
            <Select value={type} onValueChange={(value) => setType(value || "step")} disabled={isSubmitting}>
              <SelectTrigger className="h-9 bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-md text-sm text-primary focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0 focus:border-[var(--interactive-default)]">
                <SelectValue placeholder="Select a type" />
              </SelectTrigger>
              <SelectContent className="bg-[var(--surface-raised)] border-[var(--border-default)] rounded-md">
                {STEP_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value} className="text-sm text-primary focus:bg-[var(--border-default)] focus:text-primary cursor-pointer">{t.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Description <span className="text-[var(--text-muted)] font-normal">(optional)</span></Label>
            <Textarea placeholder="Describe what this step does..." value={description} onChange={(e) => setDescription(e.target.value)} className="min-h-[80px] bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-md text-sm text-primary placeholder:text-[var(--text-muted)] resize-vertical focus:border-[var(--interactive-default)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0" disabled={isSubmitting} />
          </div>
        </div>
        <DialogFooter className="h-16 px-4 border-t border-[var(--border-default)] flex items-center justify-end gap-2 shrink-0">
          <Button variant="secondary" onClick={handleCancel} disabled={isSubmitting} className="h-9 px-4 border-[var(--border-default)] bg-transparent hover:bg-[var(--surface-raised)] text-primary">Cancel</Button>
          <Button onClick={handleSubmit} disabled={!isNameFilled || isSubmitting} className="h-9 px-4 bg-[var(--interactive-default)] hover:bg-[var(--interactive-hover)] text-on-accent disabled:opacity-40">
            {isSubmitting ? (<><div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin mr-2" />Creating...</>) : (<><Plus className="w-4 h-4 mr-2" />Create Step</>)}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface EditStepModalProps {
  item: StepResponse | null;
  open: boolean;
  onClose: () => void;
}

export function EditStepModal({ item: step, open, onClose }: EditStepModalProps) {
  const updateStep = useUpdateStep();
  const [name, setName] = useState("");
  const [type, setType] = useState("step");
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (step && open) {
      setName(step.name || "");
      setType(step.type || "step");
      setDescription(step.description || "");
    }
  }, [step, open]);

  const handleSubmit = async () => {
    if (!step || isSubmitting) return;
    setIsSubmitting(true);
    try {
      await updateStep.mutateAsync({ id: step.id, data: { name: name.trim() || null, type: type || null, description: description.trim() || null } });
      onClose();
    } catch (error) {
      console.error("Failed to update step:", error);
      setIsSubmitting(false);
    }
  };

  const handleCancel = () => { if (!isSubmitting) onClose(); };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && handleCancel()}>
      <DialogContent className="w-[560px] max-w-[560px] p-0 gap-0 bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-xl overflow-hidden">
        <DialogHeader className="h-14 px-4 border-b border-[var(--border-default)] flex flex-row items-center justify-between shrink-0">
          <DialogTitle className="text-base font-medium text-primary tracking-tight">Edit Step</DialogTitle>
        </DialogHeader>
        <div className="p-4 space-y-4">
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Name</Label>
            <Input type="text" placeholder="Enter step name..." value={name} onChange={(e) => setName(e.target.value)} className="h-9 bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-md text-sm text-primary placeholder:text-[var(--text-muted)] focus:border-[var(--interactive-default)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0" disabled={isSubmitting} />
          </div>
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Type</Label>
            <Select value={type} onValueChange={(value) => setType(value || "step")} disabled={isSubmitting}>
              <SelectTrigger className="h-9 bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-md text-sm text-primary focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0 focus:border-[var(--interactive-default)]"><SelectValue placeholder="Select a type" /></SelectTrigger>
              <SelectContent className="bg-[var(--surface-raised)] border-[var(--border-default)] rounded-md">
                {STEP_TYPES.map((t) => (<SelectItem key={t.value} value={t.value} className="text-sm text-primary focus:bg-[var(--border-default)] focus:text-primary cursor-pointer">{t.label}</SelectItem>))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Description</Label>
            <Textarea placeholder="Describe what this step does..." value={description} onChange={(e) => setDescription(e.target.value)} className="min-h-[80px] bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-md text-sm text-primary placeholder:text-[var(--text-muted)] resize-vertical focus:border-[var(--interactive-default)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0" disabled={isSubmitting} />
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
