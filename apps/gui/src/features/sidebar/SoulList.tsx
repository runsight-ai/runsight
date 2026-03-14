import { useState, useMemo, useEffect } from "react";
import { useSouls, useCreateSoul, useUpdateSoul, useDeleteSoul } from "@/queries/souls";
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
  Plus,
  Search,
  MoreHorizontal,
  Trash2,
  Pencil,
  Sparkles,
  AlertCircle,
  RotateCcw,
} from "lucide-react";
import type { SoulResponse } from "@/types/schemas/souls";

// Available models for multi-select
const AVAILABLE_MODELS = [
  { value: "gpt-4o", label: "GPT-4o" },
  { value: "gpt-4o-mini", label: "GPT-4o Mini" },
  { value: "claude-3-5-sonnet", label: "Claude 3.5 Sonnet" },
  { value: "claude-3-haiku", label: "Claude 3 Haiku" },
  { value: "gemini-1.5-pro", label: "Gemini 1.5 Pro" },
  { value: "gemini-1.5-flash", label: "Gemini 1.5 Flash" },
];

function truncateText(text: string | null | undefined, maxLength: number): string {
  if (!text) return "—";
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + "...";
}

// New Soul Modal Component
interface NewSoulModalProps {
  open: boolean;
  onClose: () => void;
}

function NewSoulModal({ open, onClose }: NewSoulModalProps) {
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
    if (!isSubmitting) {
      onClose();
    }
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
          {/* Name Field */}
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

          {/* System Prompt Field */}
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

          {/* Models Multi-Select */}
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
          <Button
            variant="outline"
            onClick={handleCancel}
            disabled={isSubmitting}
            className="h-9 px-4 border-[var(--input)] bg-transparent hover:bg-[var(--surface-elevated)] text-foreground"
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!isNameFilled || isSubmitting}
            className="h-9 px-4 bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-white disabled:opacity-40"
          >
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

// Edit Soul Modal Component
interface EditSoulModalProps {
  soul: SoulResponse | null;
  open: boolean;
  onClose: () => void;
}

function EditSoulModal({ soul, open, onClose }: EditSoulModalProps) {
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
    if (!isSubmitting) {
      onClose();
    }
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
          {/* Name Field */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Name
            </Label>
            <Input
              type="text"
              placeholder="Enter soul name..."
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-9 bg-[var(--card)] border-[var(--border)] rounded-md text-sm text-foreground placeholder:text-[var(--muted-subtle)] focus:border-[var(--primary)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0"
              disabled={isSubmitting}
            />
          </div>

          {/* System Prompt Field */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              System Prompt
            </Label>
            <Textarea
              placeholder="Enter the system prompt that defines this soul's behavior..."
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              className="min-h-[100px] bg-[var(--card)] border-[var(--border)] rounded-md text-sm text-foreground placeholder:text-[var(--muted-subtle)] resize-vertical focus:border-[var(--primary)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0"
              disabled={isSubmitting}
            />
          </div>

          {/* Models Multi-Select */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Models
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
          </div>
        </div>

        <DialogFooter className="h-16 px-4 border-t border-[var(--border)] flex items-center justify-end gap-2 shrink-0">
          <Button
            variant="outline"
            onClick={handleCancel}
            disabled={isSubmitting}
            className="h-9 px-4 border-[var(--input)] bg-transparent hover:bg-[var(--surface-elevated)] text-foreground"
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="h-9 px-4 bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-white disabled:opacity-40"
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
  const { data: soulsData, isLoading, error, refetch } = useSouls();
  const deleteSoul = useDeleteSoul();

  const [searchQuery, setSearchQuery] = useState("");
  const [showNewSoulModal, setShowNewSoulModal] = useState(false);
  const [soulToEdit, setSoulToEdit] = useState<SoulResponse | null>(null);
  const [soulToDelete, setSoulToDelete] = useState<SoulResponse | null>(null);

  const souls = soulsData?.items || [];
  const totalCount = soulsData?.total || 0;

  // Filter souls by search
  const filteredSouls = useMemo(() => {
    if (!searchQuery.trim()) return souls;
    const query = searchQuery.toLowerCase();
    return souls.filter(
      (s) =>
        (s.name || "").toLowerCase().includes(query) ||
        (s.system_prompt || "").toLowerCase().includes(query)
    );
  }, [souls, searchQuery]);

  const handleDelete = async () => {
    if (!soulToDelete) return;
    try {
      await deleteSoul.mutateAsync(soulToDelete.id);
      setSoulToDelete(null);
    } catch (err) {
      console.error("Failed to delete soul:", err);
    }
  };

  // Table columns definition
  const columns: Column[] = [
    {
      key: "name",
      header: "Name",
      width: "1.5fr",
      render: (row) => {
        const soul = row as SoulResponse;
        return (
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-md flex items-center justify-center shrink-0 bg-[var(--primary-12)] text-[var(--primary)]">
              <Sparkles className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <div className="text-sm font-medium text-foreground truncate">{soul.name || "Unnamed Soul"}</div>
            </div>
          </div>
        );
      },
    },
    {
      key: "system_prompt",
      header: "System Prompt",
      width: "3fr",
      render: (row) => {
        const soul = row as SoulResponse;
        return (
          <div className="text-sm text-muted-foreground truncate max-w-[400px]">
            {truncateText(soul.system_prompt, 80)}
          </div>
        );
      },
    },
    {
      key: "models",
      header: "Models",
      width: "2fr",
      render: (row) => {
        const soul = row as SoulResponse;
        const models = soul.models || [];
        return (
          <div className="flex flex-wrap gap-1">
            {models.length === 0 ? (
              <span className="text-sm text-muted-foreground">—</span>
            ) : (
              models.map((model) => (
                <Badge
                  key={model}
                  variant="secondary"
                  className="bg-[var(--primary-12)] text-[var(--primary)] border-none text-xs"
                >
                  {model}
                </Badge>
              ))
            )}
          </div>
        );
      },
    },
    {
      key: "actions",
      header: "",
      width: "48px",
      render: (row) => {
        const soul = row as SoulResponse;
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
                    setSoulToEdit(soul);
                  }}
                >
                  <Pencil className="h-4 w-4 mr-2" />
                  Edit
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={(e) => {
                    e.stopPropagation();
                    setSoulToDelete(soul);
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
      <div className="flex-1 flex flex-col bg-[var(--background)]">
        <PageHeader title="Souls" subtitle="Loading..." />
        <div className="flex-1 p-6">
          <div className="bg-[var(--card)] border border-[var(--border)] rounded-lg overflow-hidden">
            <div className="h-14 border-b border-[var(--border)] flex items-center px-4">
              <div className="h-4 w-32 bg-[var(--border)] rounded animate-pulse" />
            </div>
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-16 border-b border-[var(--border)] flex items-center px-4 gap-4">
                <div className="h-10 w-10 bg-[var(--border)] rounded-md animate-pulse" />
                <div className="flex-1">
                  <div className="h-4 w-48 bg-[var(--border)] rounded animate-pulse mb-2" />
                  <div className="h-3 w-32 bg-[var(--border)] rounded animate-pulse" />
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
      <div className="flex-1 flex flex-col bg-[var(--background)]">
        <PageHeader title="Souls" />
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="text-center max-w-md">
            <AlertCircle className="h-12 w-12 mx-auto mb-4 text-destructive" />
            <h3 className="text-lg font-medium text-foreground mb-2">Failed to load souls</h3>
            <p className="text-sm text-muted-foreground mb-4">
              {error instanceof Error ? error.message : "An error occurred while fetching souls."}
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

  // Empty state - no souls at all
  if (souls.length === 0) {
    return (
      <div className="flex-1 flex flex-col bg-[var(--background)]">
        <PageHeader
          title="Souls"
          subtitle="0 souls"
          actions={
            <Button
              className="h-9 px-4 bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-white"
              onClick={() => setShowNewSoulModal(true)}
            >
              <Plus className="w-4 h-4 mr-2" />
              New Soul
            </Button>
          }
        />
        <div className="flex-1 flex items-center justify-center p-8">
          <EmptyState
            icon={Sparkles}
            title="No souls configured"
            description="Create your first soul to define AI personalities and behaviors."
            action={{
              label: "Create Soul",
              onClick: () => setShowNewSoulModal(true),
            }}
          />
        </div>
        <NewSoulModal open={showNewSoulModal} onClose={() => setShowNewSoulModal(false)} />
      </div>
    );
  }

  const hasSearchResults = filteredSouls.length > 0;

  return (
    <div className="flex-1 flex flex-col bg-[var(--background)]">
      {/* Page Header */}
      <PageHeader
        title="Souls"
        subtitle={`${totalCount} soul${totalCount !== 1 ? "s" : ""}`}
        actions={
          <Button
            className="h-9 px-4 bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-white"
            onClick={() => setShowNewSoulModal(true)}
          >
            <Plus className="w-4 h-4 mr-2" />
            New Soul
          </Button>
        }
      />

      {/* Search Bar */}
      <div className="h-14 border-b border-[var(--border)] flex items-center gap-3 px-4 bg-[var(--card)]">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search souls..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Search souls"
            className="h-9 pl-9 bg-[var(--background)] border-[var(--border)] rounded-md text-sm text-foreground placeholder:text-[var(--muted-subtle)] focus:border-[var(--primary)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0"
          />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {!hasSearchResults ? (
          <div className="flex items-center justify-center h-full">
            <EmptyState
              icon={Search}
              title="No souls match your search"
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
            data={filteredSouls.map((s) => s as Record<string, unknown>)}
            className="bg-[var(--card)] border border-[var(--border)] rounded-lg overflow-hidden"
            onRowClick={(row) => setSoulToEdit(row as SoulResponse)}
          />
        )}
      </div>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!soulToDelete} onOpenChange={() => setSoulToDelete(null)}>
        <DialogContent className="bg-[var(--card)] border-[var(--border)] rounded-xl">
          <DialogHeader>
            <DialogTitle className="text-base font-medium text-foreground">Delete Soul</DialogTitle>
            <DialogDescription className="text-sm text-muted-foreground">
              Are you sure you want to delete &quot;{soulToDelete?.name || "Unnamed Soul"}&quot;? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex justify-end gap-2 mt-4">
            <Button
              variant="outline"
              onClick={() => setSoulToDelete(null)}
              className="h-9 px-4 border-[var(--input)] bg-transparent hover:bg-[var(--surface-elevated)] text-foreground"
            >
              Cancel
            </Button>
            <Button
              onClick={handleDelete}
              disabled={deleteSoul.isPending}
              className="h-9 px-4 bg-destructive hover:bg-destructive/90 text-white"
            >
              {deleteSoul.isPending ? (
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

      {/* New Soul Modal */}
      <NewSoulModal open={showNewSoulModal} onClose={() => setShowNewSoulModal(false)} />

      {/* Edit Soul Modal */}
      <EditSoulModal
        soul={soulToEdit}
        open={!!soulToEdit}
        onClose={() => setSoulToEdit(null)}
      />
    </div>
  );
}
