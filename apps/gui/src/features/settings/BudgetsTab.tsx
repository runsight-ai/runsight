import { useState } from "react";
import {
  useBudgets,
  useCreateBudget,
  useUpdateBudget,
  useDeleteBudget,
} from "@/queries/settings";
import { Button } from "@/components/ui/button";
import { BudgetDialog } from "./BudgetDialog";
import { Plus, Pencil, Trash2, Wallet } from "lucide-react";
import { toast } from "sonner";
import type { Budget, CreateBudget } from "@/types/schemas/settings";
import { cn } from "@/utils/helpers";

function getProgressColor(pct: number): string {
  if (pct < 50) return "bg-[var(--success)]";
  if (pct < 80) return "bg-[var(--warning)]";
  return "bg-[var(--error)]";
}

function BudgetCard({
  budget,
  onEdit,
  onDelete,
}: {
  budget: Budget;
  onEdit: (b: Budget) => void;
  onDelete: (id: string) => void;
}) {
  const pct = budget.limit_usd > 0
    ? Math.min(100, (budget.spent_usd / budget.limit_usd) * 100)
    : 0;

  return (
    <div className="rounded-lg border border-border bg-card p-4 transition-colors hover:border-border/80">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <h3 className="text-base font-medium text-foreground">{budget.name}</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Limit: ${budget.limit_usd.toFixed(2)} / {budget.period}
          </p>
          <div className="mt-3">
            <div className="mb-1 flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Spent</span>
              <span className="font-medium text-foreground">
                ${budget.spent_usd.toFixed(2)} of ${budget.limit_usd.toFixed(2)}
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                className={cn(
                  "h-full rounded-full transition-all",
                  getProgressColor(pct)
                )}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        </div>
        <div className="ml-4 flex shrink-0 items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => onEdit(budget)}
            title="Edit budget"
          >
            <Pencil className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => onDelete(budget.id)}
            className="text-[var(--error)] hover:text-[var(--error)]"
            title="Delete budget"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}

function EmptyBudgetsState({ onAdd }: { onAdd: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 rounded-lg border border-dashed border-border bg-card/50 p-12 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-muted">
        <Wallet className="h-6 w-6 text-muted-foreground" />
      </div>
      <div className="flex flex-col gap-1">
        <h3 className="text-sm font-medium text-foreground">
          No budgets configured
        </h3>
        <p className="max-w-xs text-xs text-muted-foreground">
          Set per-workflow cost limits with 80% warning thresholds and 100%
          auto-pause to control spending.
        </p>
      </div>
      <Button onClick={onAdd} size="sm">
        <Plus className="mr-1 h-4 w-4" />
        Create Budget
      </Button>
    </div>
  );
}

export function BudgetsTab() {
  const { data, isLoading } = useBudgets();
  const createBudget = useCreateBudget();
  const updateBudget = useUpdateBudget();
  const deleteBudget = useDeleteBudget();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Budget | null>(null);
  const budgets = data?.items ?? [];

  const handleCreate = () => {
    setEditing(null);
    setDialogOpen(true);
  };

  const handleEdit = (budget: Budget) => {
    setEditing(budget);
    setDialogOpen(true);
  };

  const handleCloseDialog = (open: boolean) => {
    if (!open) {
      setDialogOpen(false);
      setEditing(null);
    }
  };

  const handleSubmit = async (data: CreateBudget) => {
    try {
      if (editing) {
        await updateBudget.mutateAsync({ id: editing.id, data });
        toast.success("Budget updated");
      } else {
        await createBudget.mutateAsync(data);
        toast.success("Budget created");
      }
    } catch {
      toast.error(editing ? "Failed to update budget" : "Failed to create budget");
      throw new Error("Save failed");
    }
  };

  const handleDelete = (id: string) => {
    if (confirm("Are you sure you want to delete this budget?")) {
      deleteBudget.mutate(id, {
        onSuccess: () => toast.success("Budget deleted"),
        onError: () => toast.error("Failed to delete budget"),
      });
    }
  };

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-2xl font-semibold tracking-tight text-foreground">
          Budgets
        </h2>
        <Button onClick={handleCreate}>
          <Plus className="mr-1 h-4 w-4" />
          Create Budget
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[1, 2].map((i) => (
            <div
              key={i}
              className="h-40 animate-pulse rounded-lg border border-border bg-card"
            />
          ))}
        </div>
      ) : budgets.length === 0 ? (
        <EmptyBudgetsState onAdd={handleCreate} />
      ) : (
        <div className="space-y-4">
          {budgets.map((budget) => (
            <BudgetCard
              key={budget.id}
              budget={budget}
              onEdit={handleEdit}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}

      <BudgetDialog
        open={dialogOpen}
        onOpenChange={handleCloseDialog}
        editing={editing}
        onSubmit={handleSubmit}
      />
    </div>
  );
}
