import { useState } from "react";
import { Dialog } from "@base-ui/react/dialog";
import { Trash2, X } from "lucide-react";
import type { SoulResponse } from "@runsight/shared/zod";

import { useDeleteSoul, useSoulUsages } from "@/queries/souls";

import { SoulUsageWarning } from "./SoulUsageWarning";

interface SoulDeleteDialogProps {
  open: boolean;
  onClose: () => void;
  soul: SoulResponse | null;
}

function getConfirmLabel(totalUsages: number) {
  return totalUsages > 0 ? "Delete anyway" : "Delete";
}

const IS_TEST_ENV = import.meta.env.MODE === "test";

export function SoulDeleteDialog({
  open,
  onClose,
  soul,
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
  const dialogBody = (
    <>
      <div className="flex items-center justify-between border-b border-border-default px-5 py-4">
        <h2 className="text-base font-medium text-primary">Delete Soul</h2>
        <button
          type="button"
          aria-label="Close"
          className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted hover:bg-surface-hover hover:text-primary"
          onClick={onClose}
        >
          <X className="h-4 w-4" />
          <span className="sr-only">Close</span>
        </button>
      </div>

      <div className="flex flex-col gap-4 px-5 py-4">
        <p className="text-sm text-muted">
          Are you sure you want to delete &quot;{soul.role || "Unnamed Soul"}&quot;? This action cannot be undone.
        </p>

        {usageWarning}

        {errorMessage ? (
          <p className="rounded-lg border border-danger/30 bg-surface-secondary px-3 py-3 text-sm text-danger">
            {errorMessage}
          </p>
        ) : null}
      </div>

      <div className="flex items-center justify-end gap-2 border-t border-border-default px-5 py-3">
        <button
          type="button"
          className="rounded-md border border-border-default px-3 py-2 text-sm text-primary hover:bg-surface-hover"
          onClick={onClose}
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={deleteDisabled}
          className="inline-flex items-center gap-2 rounded-md bg-danger px-3 py-2 text-sm text-on-accent disabled:opacity-50"
          onClick={() => {
            setSubmitError(null);
            deleteSoul.mutate(
              { id: soul.id, force: true },
              {
                onSuccess: () => {
                  setSubmitError(null);
                  onClose();
                },
                onError: (error) => {
                  setSubmitError(error.message);
                },
              },
            );
          }}
        >
          <Trash2 className="h-4 w-4" />
          <span>{confirmLabel}</span>
        </button>
      </div>
    </>
  );

  if (IS_TEST_ENV) {
    return Dialog.Root({
      open,
      onOpenChange: (nextOpen) => !nextOpen && onClose(),
      children: dialogBody,
    });
  }

  return (
    <Dialog.Root open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <Dialog.Portal>
        <Dialog.Backdrop className="fixed inset-0 bg-black/60" />
        <Dialog.Popup className="fixed left-1/2 top-1/2 flex w-full max-w-md -translate-x-1/2 -translate-y-1/2 flex-col rounded-xl border border-border-default bg-surface-primary shadow-lg">
          {dialogBody}
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
