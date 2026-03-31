import { useState } from "react";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@runsight/ui/dialog";
import { Button } from "@runsight/ui/button";
import { Trash2, X } from "lucide-react";
import type { SoulResponse } from "@runsight/shared/zod";

import { useDeleteSoul, useSoulUsages } from "@/queries/souls";

import { SoulUsageWarning } from "./SoulUsageWarning";

interface SoulDeleteDialogProps {
  open: boolean;
  onClose: () => void;
  soul: SoulResponse | null;
  onDeleted?: () => void;
}

function getConfirmLabel(totalUsages: number) {
  return totalUsages > 0 ? "Delete anyway" : "Delete";
}

export function SoulDeleteDialog({
  open,
  onClose,
  soul,
  onDeleted,
}: SoulDeleteDialogProps) {
  const soulId = open && soul ? soul.id : undefined;
  const usagesQuery = useSoulUsages(soulId);
  const deleteSoul = useDeleteSoul();
  const [submitError, setSubmitError] = useState<string | null>(null);

  if (!soul) {
    return null;
  }

  const usageCount = usagesQuery.data?.total ?? 0;
  const confirmLabel = getConfirmLabel(usageCount);
  const deleteDisabled = usagesQuery.isLoading || deleteSoul.isPending;
  const errorMessage = submitError ?? deleteSoul.error?.message;
  const usageWarning = SoulUsageWarning({
    isLoading: usagesQuery.isLoading,
    isError: usagesQuery.isError,
    errorMessage: usagesQuery.error?.message,
    usageData: usagesQuery.data,
  });

  return Dialog({
    open,
    onOpenChange: (nextOpen: boolean) => !nextOpen && onClose(),
    children: (
      DialogContent({
        showCloseButton: false,
        className: "bg-surface-primary border-border-default",
        children: (
          <>
            {DialogHeader({
              className: "items-center",
              children: (
                <>
                  {DialogTitle({
                    className: "text-base font-medium text-primary",
                    children: "Delete Soul",
                  })}
                  {Button({
                    type: "button",
                    variant: "ghost",
                    size: "icon-sm",
                    "aria-label": "Close",
                    onClick: onClose,
                    children: (
                      <>
                        <X className="h-4 w-4" />
                        <span className="sr-only">Close</span>
                      </>
                    ),
                  })}
                </>
              ),
            })}
            {DialogBody({
              className: "flex flex-col gap-4",
              children: (
                <>
                  {DialogDescription({
                    className: "text-sm text-muted",
                    children: `Are you sure you want to delete "${soul.role || "Unnamed Soul"}"? This action cannot be undone.`,
                  })}
                  {usageWarning}
                  {errorMessage ? (
                    <p className="rounded-lg border border-danger/30 bg-surface-secondary px-3 py-3 text-sm text-danger">
                      {errorMessage}
                    </p>
                  ) : null}
                </>
              ),
            })}
            {DialogFooter({
              children: (
                <>
                  {Button({
                    type: "button",
                    variant: "secondary",
                    onClick: onClose,
                    children: "Cancel",
                  })}
                  {Button({
                    type: "button",
                    variant: "danger",
                    disabled: deleteDisabled,
                    onClick: () => {
                      setSubmitError(null);
                      deleteSoul.mutate(
                        { id: soul.id, force: true },
                        {
                          onSuccess: () => {
                            setSubmitError(null);
                            onClose();
                            onDeleted?.();
                          },
                          onError: (error) => {
                            setSubmitError(error.message);
                          },
                        },
                      );
                    },
                    children: (
                      <>
                        <Trash2 className="h-4 w-4" />
                        <span>{confirmLabel}</span>
                      </>
                    ),
                  })}
                </>
              ),
            })}
          </>
        ),
      })
    ),
  });
}
