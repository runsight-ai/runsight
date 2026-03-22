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
import type { SoulResponse } from "@/types/schemas/souls";

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
      <DialogContent className="w-[560px] max-w-[560px] p-0 gap-0 bg-[var(--card)] border-[var(--border)] rounded-xl overflow-hidden">
        <DialogHeader className="h-14 px-4 border-b border-[var(--border)] flex flex-row items-center justify-between shrink-0">
          <DialogTitle className="text-base font-medium text-foreground tracking-tight">
            New Soul
          </DialogTitle>
        </DialogHeader>
        <div className="p-4 space-y-4">
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Name <span className="text-[var(--error)]">*</span>
            </Label>
            <Input
              type="text"
              placeholder="Enter soul name..."
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-9 bg-[var(--card)] border-[var(--border)] rounded-md text-sm text-foreground placeholder:text-[var(--muted-subtle)] focus:border-[var(--primary)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0"
              disabled={isSubmitting}
            />
            <p className="text-xs text-[var(--muted-subtle)]">A unique name to identify this soul</p>
          </div>
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              System Prompt <span className="text-[var(--muted-subtle)] font-normal">(optional)</span>
            </Label>
            <Textarea
              placeholder="Enter the system prompt that defines this soul's behavior..."
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              className="min-h-[100px] bg-[var(--card)] border-[var(--border)] rounded-md text-sm text-foreground placeholder:text-[var(--muted-subtle)] resize-vertical focus:border-[var(--primary)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0"
              disabled={isSubmitting}
            />
            <p className="text-xs text-[var(--muted-subtle)]">Defines the personality and behavior of this soul</p>
          </div>
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Models <span className="text-[var(--muted-subtle)] font-normal">(optional)</span>
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
                      ? "bg-[var(--primary)] text-white"
                      : "bg-[var(--background)] border border-[var(--border)] text-muted-foreground hover:border-[var(--primary)]"
                  } disabled:opacity-50`}
                >
                  {model.label}
                </button>
              ))}
            </div>
            <p className="text-xs text-[var(--muted-subtle)]">Select the models this soul can use</p>
          </div>
        </div>
        <DialogFooter className="h-16 px-4 border-t border-[var(--border)] flex items-center justify-end gap-2 shrink-0">
          <Button variant="outline" onClick={handleCancel} disabled={isSubmitting} className="h-9 px-4 border-[var(--input)] bg-transparent hover:bg-[var(--surface-elevated)] text-foreground">
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!isNameFilled || isSubmitting} className="h-9 px-4 bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-white disabled:opacity-40">
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
      <DialogContent className="w-[560px] max-w-[560px] p-0 gap-0 bg-[var(--card)] border-[var(--border)] rounded-xl overflow-hidden">
        <DialogHeader className="h-14 px-4 border-b border-[var(--border)] flex flex-row items-center justify-between shrink-0">
          <DialogTitle className="text-base font-medium text-foreground tracking-tight">
            Edit Soul
          </DialogTitle>
        </DialogHeader>
        <div className="p-4 space-y-4">
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Name</Label>
            <Input type="text" placeholder="Enter soul name..." value={name} onChange={(e) => setName(e.target.value)} className="h-9 bg-[var(--card)] border-[var(--border)] rounded-md text-sm text-foreground placeholder:text-[var(--muted-subtle)] focus:border-[var(--primary)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0" disabled={isSubmitting} />
          </div>
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">System Prompt</Label>
            <Textarea placeholder="Enter the system prompt that defines this soul's behavior..." value={systemPrompt} onChange={(e) => setSystemPrompt(e.target.value)} className="min-h-[100px] bg-[var(--card)] border-[var(--border)] rounded-md text-sm text-foreground placeholder:text-[var(--muted-subtle)] resize-vertical focus:border-[var(--primary)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0" disabled={isSubmitting} />
          </div>
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Models</Label>
            <div className="flex flex-wrap gap-2">
              {AVAILABLE_MODELS.map((model) => (
                <button key={model.value} type="button" onClick={() => toggleModel(model.value)} disabled={isSubmitting} className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${selectedModels.includes(model.value) ? "bg-[var(--primary)] text-white" : "bg-[var(--background)] border border-[var(--border)] text-muted-foreground hover:border-[var(--primary)]"} disabled:opacity-50`}>
                  {model.label}
                </button>
              ))}
            </div>
          </div>
        </div>
        <DialogFooter className="h-16 px-4 border-t border-[var(--border)] flex items-center justify-end gap-2 shrink-0">
          <Button variant="outline" onClick={handleCancel} disabled={isSubmitting} className="h-9 px-4 border-[var(--input)] bg-transparent hover:bg-[var(--surface-elevated)] text-foreground">Cancel</Button>
          <Button onClick={handleSubmit} disabled={isSubmitting} className="h-9 px-4 bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-white disabled:opacity-40">
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
