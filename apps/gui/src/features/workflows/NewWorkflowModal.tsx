import { useState, useEffect } from "react";
import { useNavigate } from "react-router";
import { useCreateWorkflow } from "@/queries/workflows";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
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
        blocks: {},
        edges: [],
      });

      if (result?.id) {
        onClose();
        navigate(`/workflows/${result.id}`);
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
      <DialogContent className="w-[480px] max-w-[480px] p-0 gap-0 bg-[#16161C] border-[#2D2D35] rounded-xl overflow-hidden">
        <DialogHeader className="h-14 px-4 border-b border-[#2D2D35] flex flex-row items-center justify-between shrink-0">
          <DialogTitle className="text-base font-medium text-foreground tracking-tight">
            Create New Workflow
          </DialogTitle>
        </DialogHeader>

        <div className="p-4 space-y-4">
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Name <span className="text-[#E53935]">*</span>
            </Label>
            <Input
              type="text"
              placeholder="Enter workflow name..."
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
              className="h-9 bg-[#16161C] border-[#2D2D35] rounded-md text-sm text-foreground placeholder:text-[#5E5E6B] focus:border-[#5E6AD2] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0"
              disabled={isSubmitting}
              autoFocus
            />
          </div>

          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Description <span className="text-[#5E5E6B] font-normal">(optional)</span>
            </Label>
            <Textarea
              placeholder="Describe what this workflow does..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="min-h-[80px] bg-[#16161C] border-[#2D2D35] rounded-md text-sm text-foreground placeholder:text-[#5E5E6B] resize-vertical focus:border-[#5E6AD2] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0"
              disabled={isSubmitting}
            />
          </div>

          {error && (
            <div className="p-3 bg-[rgba(229,57,53,0.08)] border border-[rgba(229,57,53,0.2)] rounded-md">
              <p className="text-xs text-[#E53935]">{error}</p>
            </div>
          )}
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
