import { useState, useEffect } from "react";
import { useCreateSoul, useUpdateSoul } from "@/queries/souls";
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
import { Plus, Pencil } from "lucide-react";
import type { SoulResponse } from "@/types/generated/zod";

const AVAILABLE_MODELS = [
  { value: "gpt-4o", label: "GPT-4o" },
  { value: "gpt-4o-mini", label: "GPT-4o Mini" },
  { value: "claude-3-5-sonnet", label: "Claude 3.5 Sonnet" },
  { value: "claude-3-haiku", label: "Claude 3 Haiku" },
  { value: "gemini-1.5-pro", label: "Gemini 1.5 Pro" },
  { value: "gemini-1.5-flash", label: "Gemini 1.5 Flash" },
];

interface NewSoulModalProps {
  open: boolean;
  onClose: () => void;
}

export function NewSoulModal({ open, onClose }: NewSoulModalProps) {
  const createSoul = useCreateSoul();
  const [name, setName] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isNameFilled = name.trim().length > 0;

  useEffect(() => {
    if (!open) {
      setName("");
      setSystemPrompt("");
      setSelectedModels([]);
      setIsSubmitting(false);
    }
  }, [open]);

  const handleSubmit = async () => {
    if (!isNameFilled || isSubmitting) return;
    setIsSubmitting(true);
    try {
      await createSoul.mutateAsync({
        name: name.trim(),
        system_prompt: systemPrompt.trim() || null,
        models: selectedModels.length > 0 ? selectedModels : null,
      });
      onClose();
    } catch (error) {
      console.error("Failed to create soul:", error);
      setIsSubmitting(false);
    }
  };

  const handleCancel = () => {
    if (!isSubmitting) onClose();
  };

  const toggleModel = (model: string) => {
    setSelectedModels((prev) =>
      prev.includes(model) ? prev.filter((m) => m !== model) : [...prev, model]
    );
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && handleCancel()}>
      <DialogContent className="w-[560px] max-w-[560px] p-0 gap-0 bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-xl overflow-hidden">
        <DialogHeader className="h-14 px-4 border-b border-[var(--border-default)] flex flex-row items-center justify-between shrink-0">
          <DialogTitle className="text-base font-medium text-primary tracking-tight">
            New Soul
          </DialogTitle>
        </DialogHeader>
        <div className="p-4 space-y-4">
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted">
              Name <span className="text-[var(--danger-9)]">*</span>
            </Label>
            <Input
              type="text"
              placeholder="Enter soul name..."
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-9 bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-md text-sm text-primary placeholder:text-[var(--text-muted)] focus:border-[var(--interactive-default)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0"
              disabled={isSubmitting}
            />
            <p className="text-xs text-[var(--text-muted)]">A unique name to identify this soul</p>
          </div>
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted">
              System Prompt <span className="text-[var(--text-muted)] font-normal">(optional)</span>
            </Label>
            <Textarea
              placeholder="Enter the system prompt that defines this soul's behavior..."
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              className="min-h-[100px] bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-md text-sm text-primary placeholder:text-[var(--text-muted)] resize-vertical focus:border-[var(--interactive-default)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0"
              disabled={isSubmitting}
            />
            <p className="text-xs text-[var(--text-muted)]">Defines the personality and behavior of this soul</p>
          </div>
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted">
              Models <span className="text-[var(--text-muted)] font-normal">(optional)</span>
            </Label>
            <div className="flex flex-wrap gap-2">
              {AVAILABLE_MODELS.map((model) => (
                <button
                  key={model.value}
                  type="button"
                  onClick={() => toggleModel(model.value)}
                  disabled={isSubmitting}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    selectedModels.includes(model.value)
                      ? "bg-[var(--interactive-default)] text-on-accent"
                      : "bg-[var(--surface-primary)] border border-[var(--border-default)] text-muted hover:border-[var(--interactive-default)]"
                  } disabled:opacity-50`}
                >
                  {model.label}
                </button>
              ))}
            </div>
            <p className="text-xs text-[var(--text-muted)]">Select the models this soul can use</p>
          </div>
        </div>
        <DialogFooter className="h-16 px-4 border-t border-[var(--border-default)] flex items-center justify-end gap-2 shrink-0">
          <Button variant="secondary" onClick={handleCancel} disabled={isSubmitting} className="h-9 px-4 border-[var(--border-default)] bg-transparent hover:bg-[var(--surface-raised)] text-primary">
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!isNameFilled || isSubmitting} className="h-9 px-4 bg-[var(--interactive-default)] hover:bg-[var(--interactive-hover)] text-on-accent disabled:opacity-40">
            {isSubmitting ? (
              <>
                <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin mr-2" />
                Creating...
              </>
            ) : (
              <>
                <Plus className="w-4 h-4 mr-2" />
                Create Soul
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface EditSoulModalProps {
  item: SoulResponse | null;
  open: boolean;
  onClose: () => void;
}

export function EditSoulModal({ item: soul, open, onClose }: EditSoulModalProps) {
  const updateSoul = useUpdateSoul();
  const [name, setName] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (soul && open) {
      setName(soul.name || "");
      setSystemPrompt(soul.system_prompt || "");
      setSelectedModels(soul.models || []);
    }
  }, [soul, open]);

  const handleSubmit = async () => {
    if (!soul || isSubmitting) return;
    setIsSubmitting(true);
    try {
      await updateSoul.mutateAsync({
        id: soul.id,
        data: {
          name: name.trim() || null,
          system_prompt: systemPrompt.trim() || null,
          models: selectedModels.length > 0 ? selectedModels : null,
          copy_on_edit: false,
        },
      });
      onClose();
    } catch (error) {
      console.error("Failed to update soul:", error);
      setIsSubmitting(false);
    }
  };

  const handleCancel = () => {
    if (!isSubmitting) onClose();
  };

  const toggleModel = (model: string) => {
    setSelectedModels((prev) =>
      prev.includes(model) ? prev.filter((m) => m !== model) : [...prev, model]
    );
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && handleCancel()}>
      <DialogContent className="w-[560px] max-w-[560px] p-0 gap-0 bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-xl overflow-hidden">
        <DialogHeader className="h-14 px-4 border-b border-[var(--border-default)] flex flex-row items-center justify-between shrink-0">
          <DialogTitle className="text-base font-medium text-primary tracking-tight">
            Edit Soul
          </DialogTitle>
        </DialogHeader>
        <div className="p-4 space-y-4">
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Name</Label>
            <Input type="text" placeholder="Enter soul name..." value={name} onChange={(e) => setName(e.target.value)} className="h-9 bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-md text-sm text-primary placeholder:text-[var(--text-muted)] focus:border-[var(--interactive-default)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0" disabled={isSubmitting} />
          </div>
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted">System Prompt</Label>
            <Textarea placeholder="Enter the system prompt that defines this soul's behavior..." value={systemPrompt} onChange={(e) => setSystemPrompt(e.target.value)} className="min-h-[100px] bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-md text-sm text-primary placeholder:text-[var(--text-muted)] resize-vertical focus:border-[var(--interactive-default)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0" disabled={isSubmitting} />
          </div>
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Models</Label>
            <div className="flex flex-wrap gap-2">
              {AVAILABLE_MODELS.map((model) => (
                <button key={model.value} type="button" onClick={() => toggleModel(model.value)} disabled={isSubmitting} className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${selectedModels.includes(model.value) ? "bg-[var(--interactive-default)] text-on-accent" : "bg-[var(--surface-primary)] border border-[var(--border-default)] text-muted hover:border-[var(--interactive-default)]"} disabled:opacity-50`}>
                  {model.label}
                </button>
              ))}
            </div>
          </div>
        </div>
        <DialogFooter className="h-16 px-4 border-t border-[var(--border-default)] flex items-center justify-end gap-2 shrink-0">
          <Button variant="secondary" onClick={handleCancel} disabled={isSubmitting} className="h-9 px-4 border-[var(--border-default)] bg-transparent hover:bg-[var(--surface-raised)] text-primary">Cancel</Button>
          <Button onClick={handleSubmit} disabled={isSubmitting} className="h-9 px-4 bg-[var(--interactive-default)] hover:bg-[var(--interactive-hover)] text-on-accent disabled:opacity-40">
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
