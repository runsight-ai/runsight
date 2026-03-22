import { useState, useMemo, useEffect } from "react";
import {
  useSteps,
  useCreateStep,
  useUpdateStep,
  useDeleteStep,
} from "@/queries/steps";
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
  Footprints,
  MoreHorizontal,
  Trash2,
  Pencil,
} from "lucide-react";
import type { StepResponse } from "@/types/schemas/steps";
import { truncateText } from "@/utils/formatting";
import { getStepTypeColor } from "@/utils/colors";

// Available step types
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

// New Step Modal Component
interface NewStepModalProps {
  open: boolean;
  onClose: () => void;
}

function NewStepModal({ open, onClose }: NewStepModalProps) {
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
      await createStep.mutateAsync({
        name: name.trim(),
        type,
        description: description.trim() || null,
      });
      onClose();
    } catch (error) {
      console.error("Failed to create step:", error);
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
      <DialogContent className="w-[560px] max-w-[560px] p-0 gap-0 bg-[var(--card)] border-[var(--border)] rounded-xl overflow-hidden">
        <DialogHeader className="h-14 px-4 border-b border-[var(--border)] flex flex-row items-center justify-between shrink-0">
          <DialogTitle className="text-base font-medium text-foreground tracking-tight">
            New Step
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
              placeholder="Enter step name..."
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-9 bg-[var(--card)] border-[var(--border)] rounded-md text-sm text-foreground placeholder:text-[var(--muted-subtle)] focus:border-[var(--primary)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0"
              disabled={isSubmitting}
            />
            <p className="text-xs text-[var(--muted-subtle)]">A unique name to identify this step</p>
          </div>

          {/* Type Field */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Type
            </Label>
            <Select
              value={type}
              onValueChange={(value) => setType(value || "step")}
              disabled={isSubmitting}
            >
              <SelectTrigger className="h-9 bg-[var(--card)] border-[var(--border)] rounded-md text-sm text-foreground focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0 focus:border-[var(--primary)]">
                <SelectValue placeholder="Select a type" />
              </SelectTrigger>
              <SelectContent className="bg-[var(--surface-elevated)] border-[var(--border)] rounded-md">
                {STEP_TYPES.map((t) => (
                  <SelectItem
                    key={t.value}
                    value={t.value}
                    className="text-sm text-foreground focus:bg-[var(--border)] focus:text-foreground cursor-pointer"
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
              Description <span className="text-[var(--muted-subtle)] font-normal">(optional)</span>
            </Label>
            <Textarea
              placeholder="Describe what this step does..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="min-h-[80px] bg-[var(--card)] border-[var(--border)] rounded-md text-sm text-foreground placeholder:text-[var(--muted-subtle)] resize-vertical focus:border-[var(--primary)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0"
              disabled={isSubmitting}
            />
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
                Create Step
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// Edit Step Modal Component
interface EditStepModalProps {
  step: StepResponse | null;
  open: boolean;
  onClose: () => void;
}

function EditStepModal({ step, open, onClose }: EditStepModalProps) {
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
      await updateStep.mutateAsync({
        id: step.id,
        data: {
          name: name.trim() || null,
          type: type || null,
          description: description.trim() || null,
        },
      });
      onClose();
    } catch (error) {
      console.error("Failed to update step:", error);
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
      <DialogContent className="w-[560px] max-w-[560px] p-0 gap-0 bg-[var(--card)] border-[var(--border)] rounded-xl overflow-hidden">
        <DialogHeader className="h-14 px-4 border-b border-[var(--border)] flex flex-row items-center justify-between shrink-0">
          <DialogTitle className="text-base font-medium text-foreground tracking-tight">
            Edit Step
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
              placeholder="Enter step name..."
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-9 bg-[var(--card)] border-[var(--border)] rounded-md text-sm text-foreground placeholder:text-[var(--muted-subtle)] focus:border-[var(--primary)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0"
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
              onValueChange={(value) => setType(value || "step")}
              disabled={isSubmitting}
            >
              <SelectTrigger className="h-9 bg-[var(--card)] border-[var(--border)] rounded-md text-sm text-foreground focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0 focus:border-[var(--primary)]">
                <SelectValue placeholder="Select a type" />
              </SelectTrigger>
              <SelectContent className="bg-[var(--surface-elevated)] border-[var(--border)] rounded-md">
                {STEP_TYPES.map((t) => (
                  <SelectItem
                    key={t.value}
                    value={t.value}
                    className="text-sm text-foreground focus:bg-[var(--border)] focus:text-foreground cursor-pointer"
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
              placeholder="Describe what this step does..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="min-h-[80px] bg-[var(--card)] border-[var(--border)] rounded-md text-sm text-foreground placeholder:text-[var(--muted-subtle)] resize-vertical focus:border-[var(--primary)] focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0"
              disabled={isSubmitting}
            />
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
  const { data: stepsData, isLoading, error, refetch } = useSteps();
  const deleteStep = useDeleteStep();

  const [searchQuery, setSearchQuery] = useState("");
  const [showNewStepModal, setShowNewStepModal] = useState(false);
  const [stepToEdit, setStepToEdit] = useState<StepResponse | null>(null);
  const [stepToDelete, setStepToDelete] = useState<StepResponse | null>(null);

  const steps = stepsData?.items || [];
  const totalCount = stepsData?.total || 0;

  // Filter steps by search
  const filteredSteps = useMemo(() => {
    if (!searchQuery.trim()) return steps;
    const query = searchQuery.toLowerCase();
    return steps.filter(
      (s) =>
        s.name.toLowerCase().includes(query) ||
        (s.description || "").toLowerCase().includes(query) ||
        s.type.toLowerCase().includes(query)
    );
  }, [steps, searchQuery]);

  const handleDelete = async () => {
    if (!stepToDelete) return;
    try {
      await deleteStep.mutateAsync(stepToDelete.id);
      setStepToDelete(null);
    } catch (err) {
      console.error("Failed to delete step:", err);
    }
  };

  // Table columns definition
  const columns: Column[] = [
    {
      key: "name",
      header: "Name",
      width: "1.5fr",
      render: (row) => {
        const step = row as StepResponse;
        return (
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-md flex items-center justify-center shrink-0 bg-[var(--primary-12)] text-[var(--primary)]">
              <Footprints className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <div className="text-sm font-medium text-foreground truncate">{step.name}</div>
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
        const step = row as StepResponse;
        return (
          <Badge
            variant="secondary"
            className={`${getStepTypeColor(step.type)} border-none text-xs`}
          >
            {step.type}
          </Badge>
        );
      },
    },
    {
      key: "path",
      header: "Path",
      width: "1.5fr",
      render: (row) => {
        const step = row as StepResponse;
        return (
          <div className="text-sm text-muted-foreground font-mono text-xs truncate">
            {step.path}
          </div>
        );
      },
    },
    {
      key: "description",
      header: "Description",
      width: "2fr",
      render: (row) => {
        const step = row as StepResponse;
        return (
          <div className="text-sm text-muted-foreground truncate max-w-[300px]">
            {truncateText(step.description, 60)}
          </div>
        );
      },
    },
    {
      key: "actions",
      header: "",
      width: "48px",
      render: (row) => {
        const step = row as StepResponse;
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
                    setStepToEdit(step);
                  }}
                >
                  <Pencil className="h-4 w-4 mr-2" />
                  Edit
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={(e) => {
                    e.stopPropagation();
                    setStepToDelete(step);
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
        <PageHeader title="Steps" subtitle="Loading..." />
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
        <PageHeader title="Steps" />
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="text-center max-w-md">
            <AlertCircle className="h-12 w-12 mx-auto mb-4 text-destructive" />
            <h3 className="text-lg font-medium text-foreground mb-2">Failed to load steps</h3>
            <p className="text-sm text-muted-foreground mb-4">
              {error instanceof Error ? error.message : "An error occurred while fetching steps."}
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

  // Empty state - no steps at all
  if (steps.length === 0) {
    return (
      <div className="flex-1 flex flex-col bg-[var(--background)]">
        <PageHeader
          title="Steps"
          subtitle="0 steps"
          actions={
            <Button
              className="h-9 px-4 bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-white"
              onClick={() => setShowNewStepModal(true)}
            >
              <Plus className="w-4 h-4 mr-2" />
              New Step
            </Button>
          }
        />
        <div className="flex-1 flex items-center justify-center p-8">
          <EmptyState
            icon={Footprints}
            title="No steps found"
            description="Create your first step to define workflow building blocks."
            action={{
              label: "Create Step",
              onClick: () => setShowNewStepModal(true),
            }}
          />
        </div>
        <NewStepModal open={showNewStepModal} onClose={() => setShowNewStepModal(false)} />
      </div>
    );
  }

  const hasSearchResults = filteredSteps.length > 0;

  return (
    <div className="flex-1 flex flex-col bg-[var(--background)]">
      {/* Page Header */}
      <PageHeader
        title="Steps"
        subtitle={`${totalCount} step${totalCount !== 1 ? "s" : ""}`}
        actions={
          <Button
            className="h-9 px-4 bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-white"
            onClick={() => setShowNewStepModal(true)}
          >
            <Plus className="w-4 h-4 mr-2" />
            New Step
          </Button>
        }
      />

      {/* Search Bar */}
      <div className="h-14 border-b border-[var(--border)] flex items-center gap-3 px-4 bg-[var(--card)]">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search steps..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Search steps"
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
              title="No steps match your search"
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
            data={filteredSteps.map((s) => s as Record<string, unknown>)}
            className="bg-[var(--card)] border border-[var(--border)] rounded-lg overflow-hidden"
            onRowClick={(row) => setStepToEdit(row as StepResponse)}
          />
        )}
      </div>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!stepToDelete} onOpenChange={() => setStepToDelete(null)}>
        <DialogContent className="bg-[var(--card)] border-[var(--border)] rounded-xl">
          <DialogHeader>
            <DialogTitle className="text-base font-medium text-foreground">
              Delete Step
            </DialogTitle>
            <DialogDescription className="text-sm text-muted-foreground">
              Are you sure you want to delete &quot;{stepToDelete?.name || "Unnamed Step"}&quot;?
              This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex justify-end gap-2 mt-4">
            <Button
              variant="outline"
              onClick={() => setStepToDelete(null)}
              className="h-9 px-4 border-[var(--input)] bg-transparent hover:bg-[var(--surface-elevated)] text-foreground"
            >
              Cancel
            </Button>
            <Button
              onClick={handleDelete}
              disabled={deleteStep.isPending}
              className="h-9 px-4 bg-destructive hover:bg-destructive/90 text-white"
            >
              {deleteStep.isPending ? (
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

      {/* New Step Modal */}
      <NewStepModal open={showNewStepModal} onClose={() => setShowNewStepModal(false)} />

      {/* Edit Step Modal */}
      <EditStepModal
        step={stepToEdit}
        open={!!stepToEdit}
        onClose={() => setStepToEdit(null)}
      />
    </div>
  );
}
