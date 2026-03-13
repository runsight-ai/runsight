import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { Budget, CreateBudget } from "@/types/schemas/settings";

interface BudgetDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editing?: Budget | null;
  onSubmit: (data: CreateBudget) => Promise<void>;
}

export function BudgetDialog({
  open,
  onOpenChange,
  editing,
  onSubmit,
}: BudgetDialogProps) {
  const [name, setName] = useState("");
  const [limitUsd, setLimitUsd] = useState("");
  const [period, setPeriod] = useState<"daily" | "weekly" | "monthly">("monthly");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      if (editing) {
        setName(editing.name);
        setLimitUsd(String(editing.limit_usd));
        setPeriod(editing.period);
      } else {
        setName("");
        setLimitUsd("");
        setPeriod("monthly");
      }
    }
  }, [open, editing]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const num = parseFloat(limitUsd);
    if (!name.trim() || isNaN(num) || num <= 0) return;
    setIsSubmitting(true);
    try {
      await onSubmit({ name: name.trim(), limit_usd: num, period });
      onOpenChange(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[400px]">
        <DialogHeader>
          <DialogTitle>{editing ? "Edit Budget" : "Create Budget"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="budget-name">Name</Label>
            <Input
              id="budget-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Monthly AI spend"
              className="rounded-lg border-border bg-card"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="budget-limit">Limit (USD)</Label>
            <Input
              id="budget-limit"
              type="number"
              min="0"
              step="0.01"
              value={limitUsd}
              onChange={(e) => setLimitUsd(e.target.value)}
              placeholder="10.00"
              className="rounded-lg border-border bg-card"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="budget-period">Period</Label>
            <Select
              value={period}
              onValueChange={(v) => v && setPeriod(v as "daily" | "weekly" | "monthly")}
            >
              <SelectTrigger
                id="budget-period"
                className="h-9 rounded-lg border-border bg-card"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="daily">Daily</SelectItem>
                <SelectItem value="weekly">Weekly</SelectItem>
                <SelectItem value="monthly">Monthly</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {editing ? "Save" : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
