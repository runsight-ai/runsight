import { ProviderModal } from "@/components/provider/ProviderModal";
import type { EditingProvider } from "@/components/provider/ProviderSetup";

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
  return (
    <ProviderModal
      mode={editing ? "settings-edit" : "settings-add"}
      open={open}
      onOpenChange={onOpenChange}
      editing={editing}
    />
  );
}
