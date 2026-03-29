import { useRef, useState, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@runsight/ui/dialog";
import { Button } from "@runsight/ui/button";
import { ProviderSetup } from "@/components/provider/ProviderSetup";
import type { ProviderSetupRef, ProviderSetupState, EditingProvider } from "@/components/provider/ProviderSetup";
import { useDeleteProvider } from "@/queries/settings";

interface AddProviderDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editing?: EditingProvider;
}

export function AddProviderDialog({
  open,
  onOpenChange,
  editing,
}: AddProviderDialogProps) {
  const setupRef = useRef<ProviderSetupRef>(null);
  const [state, setState] = useState<ProviderSetupState | null>(null);
  const deleteProvider = useDeleteProvider();
  const stateRef = useRef(state);
  stateRef.current = state;

  const cleanup = useCallback(() => {
    const s = stateRef.current;
    if (s?.createdProviderId && !s.isEditMode) {
      deleteProvider.mutate(s.createdProviderId);
    }
  }, [deleteProvider]);

  const handleClose = useCallback(() => {
    cleanup();
    setupRef.current?.reset();
    onOpenChange(false);
  }, [cleanup, onOpenChange]);

  const handleDone = useCallback(() => {
    setupRef.current?.reset();
    onOpenChange(false);
  }, [onOpenChange]);

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) handleClose(); }}>
      <DialogContent className="sm:max-w-[600px] max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{editing ? `Edit ${editing.name}` : "Add Provider"}</DialogTitle>
        </DialogHeader>

        <div className="py-2">
          <ProviderSetup
            ref={setupRef}
            onStateChange={setState}
            editing={editing}
          />
        </div>

        <DialogFooter>
          {state?.canStepBack && (
            <Button
              variant="secondary"
              onClick={() => setupRef.current?.stepBack()}
              type="button"
              className="mr-auto"
            >
              Back
            </Button>
          )}
          <Button variant="secondary" onClick={handleClose} type="button">
            Cancel
          </Button>
          <Button
            onClick={handleDone}
            disabled={!state?.step2Done}
            type="button"
          >
            Done
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
