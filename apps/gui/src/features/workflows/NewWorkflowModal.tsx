import { useState, useEffect } from "react";
import { useNavigate } from "react-router";
import { useCreateWorkflow } from "@/queries/workflows";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@runsight/ui/dialog";
import { Button } from "@runsight/ui/button";
import { Input } from "@runsight/ui/input";
import { Textarea } from "@runsight/ui/textarea";
import { Label } from "@runsight/ui/label";
import { ArrowRight } from "lucide-react";
import { toast } from "sonner";

interface NewWorkflowModalProps {
  open: boolean;
  onClose: () => void;
}

export function NewWorkflowModal({ open, onClose }: NewWorkflowModalProps) {
  const navigate = useNavigate();
  const createWorkflow = useCreateWorkflow();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isNameFilled = name.trim().length > 0;

  useEffect(() => {
    if (!open) {
      setName("");
      setDescription("");
      setIsSubmitting(false);
      setError(null);
    }
  }, [open]);

  const handleSubmit = async () => {
    if (!isNameFilled || isSubmitting) return;

    setIsSubmitting(true);
    setError(null);
    try {
      const result = await createWorkflow.mutateAsync({
        name: name.trim(),
        description: description.trim() || undefined,
        canvas_state: {
          nodes: [],
          edges: [],
          viewport: { x: 0, y: 0, zoom: 1 },
          selected_node_id: null,
          canvas_mode: "dag",
        },
      });

      if (result?.id) {
        onClose();
        navigate(`/workflows/${result.id}/edit`);
      } else {
        setError("Workflow was created but no ID was returned.");
        setIsSubmitting(false);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to create workflow";
      setError(message);
      toast.error("Failed to create workflow", { description: message });
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
      <DialogContent className="w-[480px] max-w-[480px] p-0 gap-0 bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-xl overflow-hidden">
        <DialogHeader className="h-14 px-4 border-b border-[var(--border-default)] flex flex-row items-center justify-between shrink-0">
          <DialogTitle className="text-base font-medium text-primary tracking-tight">
            Create New Workflow
          </DialogTitle>
        </DialogHeader>

        <div className="p-4 space-y-4">
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted">
              Name <span className="text-[var(--danger-9)]">*</span>
            </Label>
            <Input
              type="text"
              placeholder="Enter workflow name..."
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
              className="h-9 bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-md text-sm text-primary placeholder:text-[var(--text-muted)] focus:border-[var(--interactive-default)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0"
              disabled={isSubmitting}
              autoFocus
            />
          </div>

          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted">
              Description <span className="text-[var(--text-muted)] font-normal">(optional)</span>
            </Label>
            <Textarea
              placeholder="Describe what this workflow does..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="min-h-[80px] bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-md text-sm text-primary placeholder:text-[var(--text-muted)] resize-vertical focus:border-[var(--interactive-default)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0"
              disabled={isSubmitting}
            />
          </div>

          {error && (
            <div className="p-3 bg-danger-3 border border-danger-7 rounded-md">
              <p className="text-xs text-[var(--danger-9)]">{error}</p>
            </div>
          )}
        </div>

        <DialogFooter className="h-16 px-4 border-t border-[var(--border-default)] flex items-center justify-end gap-2 shrink-0">
          <Button
            variant="secondary"
            onClick={handleCancel}
            disabled={isSubmitting}
            className="h-9 px-4 border-[var(--border-default)] bg-transparent hover:bg-[var(--surface-raised)] text-primary"
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!isNameFilled || isSubmitting}
            className="h-9 px-4 bg-[var(--interactive-default)] hover:bg-[var(--interactive-hover)] text-on-accent disabled:opacity-40"
          >
            {isSubmitting ? (
              <>
                <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin mr-2" />
                Creating...
              </>
            ) : (
              <>
                Create
                <ArrowRight className="w-4 h-4 ml-2" />
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
