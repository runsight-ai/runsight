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
import type { StepResponse } from "@/types/schemas/steps";

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
      <DialogContent className="w-[560px] max-w-[560px] p-0 gap-0 bg-[var(--card)] border-[var(--border)] rounded-xl overflow-hidden">
        <DialogHeader className="h-14 px-4 border-b border-[var(--border)] flex flex-row items-center justify-between shrink-0">
          <DialogTitle className="text-base font-medium text-foreground tracking-tight">New Step</DialogTitle>
        </DialogHeader>
        <div className="p-4 space-y-4">
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Name <span className="text-[var(--error)]">*</span></Label>
            <Input type="text" placeholder="Enter step name..." value={name} onChange={(e) => setName(e.target.value)} className="h-9 bg-[var(--card)] border-[var(--border)] rounded-md text-sm text-foreground placeholder:text-[var(--muted-subtle)] focus:border-[var(--primary)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0" disabled={isSubmitting} />
            <p className="text-xs text-[var(--muted-subtle)]">A unique name to identify this step</p>
          </div>
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Type</Label>
            <Select value={type} onValueChange={(value) => setType(value || "step")} disabled={isSubmitting}>
              <SelectTrigger className="h-9 bg-[var(--card)] border-[var(--border)] rounded-md text-sm text-foreground focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0 focus:border-[var(--primary)]">
                <SelectValue placeholder="Select a type" />
              </SelectTrigger>
              <SelectContent className="bg-[var(--surface-elevated)] border-[var(--border)] rounded-md">
                {STEP_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value} className="text-sm text-foreground focus:bg-[var(--border)] focus:text-foreground cursor-pointer">{t.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Description <span className="text-[var(--muted-subtle)] font-normal">(optional)</span></Label>
            <Textarea placeholder="Describe what this step does..." value={description} onChange={(e) => setDescription(e.target.value)} className="min-h-[80px] bg-[var(--card)] border-[var(--border)] rounded-md text-sm text-foreground placeholder:text-[var(--muted-subtle)] resize-vertical focus:border-[var(--primary)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0" disabled={isSubmitting} />
          </div>
        </div>
        <DialogFooter className="h-16 px-4 border-t border-[var(--border)] flex items-center justify-end gap-2 shrink-0">
          <Button variant="outline" onClick={handleCancel} disabled={isSubmitting} className="h-9 px-4 border-[var(--input)] bg-transparent hover:bg-[var(--surface-elevated)] text-foreground">Cancel</Button>
          <Button onClick={handleSubmit} disabled={!isNameFilled || isSubmitting} className="h-9 px-4 bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-white disabled:opacity-40">
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
      <DialogContent className="w-[560px] max-w-[560px] p-0 gap-0 bg-[var(--card)] border-[var(--border)] rounded-xl overflow-hidden">
        <DialogHeader className="h-14 px-4 border-b border-[var(--border)] flex flex-row items-center justify-between shrink-0">
          <DialogTitle className="text-base font-medium text-foreground tracking-tight">Edit Step</DialogTitle>
        </DialogHeader>
        <div className="p-4 space-y-4">
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Name</Label>
            <Input type="text" placeholder="Enter step name..." value={name} onChange={(e) => setName(e.target.value)} className="h-9 bg-[var(--card)] border-[var(--border)] rounded-md text-sm text-foreground placeholder:text-[var(--muted-subtle)] focus:border-[var(--primary)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0" disabled={isSubmitting} />
          </div>
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Type</Label>
            <Select value={type} onValueChange={(value) => setType(value || "step")} disabled={isSubmitting}>
              <SelectTrigger className="h-9 bg-[var(--card)] border-[var(--border)] rounded-md text-sm text-foreground focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0 focus:border-[var(--primary)]"><SelectValue placeholder="Select a type" /></SelectTrigger>
              <SelectContent className="bg-[var(--surface-elevated)] border-[var(--border)] rounded-md">
                {STEP_TYPES.map((t) => (<SelectItem key={t.value} value={t.value} className="text-sm text-foreground focus:bg-[var(--border)] focus:text-foreground cursor-pointer">{t.label}</SelectItem>))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Description</Label>
            <Textarea placeholder="Describe what this step does..." value={description} onChange={(e) => setDescription(e.target.value)} className="min-h-[80px] bg-[var(--card)] border-[var(--border)] rounded-md text-sm text-foreground placeholder:text-[var(--muted-subtle)] resize-vertical focus:border-[var(--primary)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0" disabled={isSubmitting} />
          </div>
        </div>
        <DialogFooter className="h-16 px-4 border-t border-[var(--border)] flex items-center justify-end gap-2 shrink-0">
          <Button variant="outline" onClick={handleCancel} disabled={isSubmitting} className="h-9 px-4 border-[var(--input)] bg-transparent hover:bg-[var(--surface-elevated)] text-foreground">Cancel</Button>
          <Button onClick={handleSubmit} disabled={isSubmitting} className="h-9 px-4 bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-white disabled:opacity-40">
            {isSubmitting ? (<><div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin mr-2" />Saving...</>) : (<><Pencil className="w-4 h-4 mr-2" />Save Changes</>)}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
