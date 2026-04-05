import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@runsight/ui/dialog";
import { Button } from "@runsight/ui/button";
import { Trash2 } from "lucide-react";

interface DeleteConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  isPending: boolean;
  resourceName: string;
  itemName?: string;
}

export function DeleteConfirmDialog({
  open,
  onClose,
  onConfirm,
  isPending,
  resourceName,
  itemName,
}: DeleteConfirmDialogProps) {
  const displayName = itemName || `this ${resourceName.toLowerCase()}`;

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent
        className="bg-surface-secondary border-border-default rounded-xl"
        data-testid="delete-confirm-dialog"
      >
        <DialogHeader>
          <DialogTitle className="text-base font-medium text-primary" data-testid="delete-confirm-title">
            Delete {resourceName}
          </DialogTitle>
          <DialogDescription className="text-sm text-muted" data-testid="delete-confirm-description">
            Are you sure you want to delete &quot;{displayName}&quot;? This action cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="flex justify-end gap-2 mt-4">
          <Button
            variant="secondary"
            onClick={onClose}
            className="h-9 px-4 border-border-default bg-transparent hover:bg-surface-raised text-primary"
            data-testid="delete-confirm-cancel-button"
          >
            Cancel
          </Button>
          <Button
            onClick={onConfirm}
            disabled={isPending}
            className="h-9 px-4 bg-danger hover:bg-danger/90 text-on-accent"
            data-testid="delete-confirm-submit-button"
          >
            {isPending ? (
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
  );
}
