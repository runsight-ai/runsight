import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
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
      <DialogContent className="bg-[var(--surface-secondary)] border-[var(--border-default)] rounded-xl">
        <DialogHeader>
          <DialogTitle className="text-base font-medium text-primary">
            Delete {resourceName}
          </DialogTitle>
          <DialogDescription className="text-sm text-muted">
            Are you sure you want to delete &quot;{displayName}&quot;? This action cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="flex justify-end gap-2 mt-4">
          <Button
            variant="outline"
            onClick={onClose}
            className="h-9 px-4 border-[var(--border-default)] bg-transparent hover:bg-[var(--surface-raised)] text-primary"
          >
            Cancel
          </Button>
          <Button
            onClick={onConfirm}
            disabled={isPending}
            className="h-9 px-4 bg-danger hover:bg-danger/90 text-white"
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
