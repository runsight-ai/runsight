import { useState } from "react";
import {
  useProviders,
  useDeleteProvider,
  useTestProviderConnection,
  useUpdateProvider,
} from "@/queries/settings";
import { DeleteConfirmDialog, StatusBadge } from "@/components/shared";
import { Button } from "@runsight/ui/button";
import { Switch } from "@runsight/ui/switch";
import {
  Plus,
  Pencil,
  Trash2,
  CheckCircle2,
  XCircle,
  Server,
} from "lucide-react";
import { AddProviderDialog } from "./AddProviderDialog";
import type { EditingProvider } from "@/components/provider/ProviderSetup";
import { cn } from "@/utils/helpers";
import type { Provider } from "@/api/settings";

// Provider icon/logo component
function ProviderLogo({ name, status }: { name: string; status: string }) {
  const getInitials = (name: string) => {
    return name
      .split(/\s+/)
      .map((word) => word[0])
      .join("")
      .toUpperCase()
      .slice(0, 3);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "connected":
      case "active":
        return "text-primary";
      case "rate-limited":
        return "text-[var(--warning-9)]";
      case "error":
        return "text-[var(--danger-9)]";
      default:
        return "text-muted";
    }
  };

  return (
    <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg border border-border-default bg-surface-secondary">
      <span className={cn("text-xs font-semibold", getStatusColor(status))}>
        {getInitials(name)}
      </span>
    </div>
  );
}

// Status mapping from provider status to StatusBadge variant
function getStatusVariant(
  status: string
): "success" | "warning" | "error" | "pending" {
  switch (status) {
    case "connected":
    case "active":
      return "success";
    case "rate-limited":
      return "warning";
    case "error":
      return "error";
    default:
      return "pending";
  }
}

function getStatusLabel(status: string): string {
  switch (status) {
    case "connected":
    case "active":
      return "Active";
    case "rate-limited":
      return "Rate Limited";
    case "error":
      return "Error";
    case "offline":
      return "Offline";
    default:
      return "Unknown";
  }
}

// Provider Card Component
function ProviderCard({
  provider,
  onEdit,
  onDelete,
}: {
  provider: Provider;
  onEdit: (provider: Provider) => void;
  onDelete: (provider: Provider) => void;
}) {
  const testConnection = useTestProviderConnection();
  const updateProvider = useUpdateProvider();
  const [testStatus, setTestStatus] = useState<
    "idle" | "testing" | "success" | "error"
  >("idle");

  const handleTest = async () => {
    setTestStatus("testing");
    try {
      const result = await testConnection.mutateAsync(provider.id);
      setTestStatus(result.success ? "success" : "error");
      setTimeout(() => setTestStatus("idle"), 3000);
    } catch {
      setTestStatus("error");
      setTimeout(() => setTestStatus("idle"), 3000);
    }
  };

  const handleToggle = (enabled: boolean) => {
    updateProvider.mutate({
      id: provider.id,
      data: { name: provider.name, is_active: enabled },
    });
  };

  // Mask API key - show last 4 chars
  const maskApiKey = (key: string | null | undefined) => {
    if (!key) return "(none configured)";
    const last4 = key.slice(-4);
    return `••••••••••••••••${last4}`;
  };

  const isEnabled =
    provider.status !== "offline" && provider.status !== "error";

  return (
    <div className="rounded-lg border border-border-default bg-surface-secondary p-4 transition-colors hover:border-border-default/80">
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          <ProviderLogo name={provider.name} status={provider.status} />

          {/* Provider Info */}
          <div className="flex-1">
            <div className="mb-1 flex items-center gap-3">
              <h3 className="text-base font-medium text-primary">
                {provider.name}
              </h3>
              <div
                aria-label={`Provider ${provider.name} status ${getStatusLabel(provider.status)}`}
              >
                <StatusBadge
                  status={getStatusVariant(provider.status)}
                  label={getStatusLabel(provider.status)}
                />
              </div>
            </div>

            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <span className="w-20 text-xs uppercase tracking-wider text-muted">
                  API Key
                </span>
                {provider.api_key_env?.startsWith("$") ? (
                  <span className="font-mono text-muted">
                    Configured via {provider.api_key_env}
                  </span>
                ) : (
                  <span className="font-mono text-muted">
                    {maskApiKey(provider.api_key_env)}
                  </span>
                )}
              </div>

              {provider.base_url && (
                <div className="flex items-center gap-2">
                  <span className="w-20 text-xs uppercase tracking-wider text-muted">
                    Base URL
                  </span>
                  <span className="text-muted">
                    {provider.base_url}
                  </span>
                </div>
              )}

              <div className="mt-3 flex items-center gap-6">
                <div className="flex items-center gap-2">
                  <span className="text-xs uppercase tracking-wider text-muted">
                    Models
                  </span>
                  <span className="font-medium text-primary">
                    {provider.models?.length || 0} available
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3">
          <Switch
            checked={isEnabled}
            onCheckedChange={handleToggle}
            aria-label={`Enable ${provider.name} provider`}
          />
          <div className="flex items-center gap-1">
            <Button
              variant="secondary"
              size="sm"
              onClick={handleTest}
              disabled={testStatus === "testing"}
              className="text-xs"
              aria-label={`Test ${provider.name} connection`}
            >
              {testStatus === "testing" ? (
                "Testing..."
              ) : testStatus === "success" ? (
                <>
                  <CheckCircle2 className="mr-1 h-3 w-3 text-[var(--success-9)]" />
                  Connected
                </>
              ) : testStatus === "error" ? (
                <>
                  <XCircle className="mr-1 h-3 w-3 text-[var(--danger-9)]" />
                  Failed
                </>
              ) : (
                "Test Connection"
              )}
            </Button>
            <Button
              variant="icon-only"
              size="sm"
              onClick={() => onEdit(provider)}
              title="Edit provider"
              aria-label={`Edit ${provider.name} provider`}
            >
              <Pencil className="h-4 w-4" />
            </Button>
            <Button
              variant="icon-only"
              size="sm"
              onClick={() => onDelete(provider)}
              className="text-[var(--danger-9)] hover:text-[var(--danger-9)]"
              title="Remove provider"
              aria-label={`Delete ${provider.name} provider`}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// Empty State Component
function EmptyProvidersState({ onAdd }: { onAdd: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 rounded-lg border border-dashed border-border-default bg-surface-secondary/50 p-12 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-surface-tertiary">
        <Server className="h-6 w-6 text-muted" />
      </div>
      <div className="flex flex-col gap-1">
        <h3 className="text-sm font-medium text-primary">
          No providers configured
        </h3>
        <p className="max-w-xs text-xs text-muted">
          Add an AI provider to start using Runsight with models like GPT-4,
          Claude, or local Ollama instances.
        </p>
      </div>
      <Button onClick={onAdd} size="sm">
        <Plus className="mr-1 h-4 w-4" />
        Add Provider
      </Button>
    </div>
  );
}

function toEditing(p: Provider): EditingProvider {
  return {
    id: p.id,
    name: p.name,
    type: p.name.toLowerCase().replace(/\s+/g, "_"),
    baseUrl: p.base_url,
    hasKey: !!p.api_key_env,
  };
}

export function ProvidersTab() {
  const { data, isLoading } = useProviders();
  const deleteProvider = useDeleteProvider();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<EditingProvider | undefined>(undefined);
  const [itemToDelete, setItemToDelete] = useState<Provider | null>(null);

  const providers = data?.items || [];

  const handleAdd = () => {
    setEditing(undefined);
    setDialogOpen(true);
  };

  const handleEdit = (provider: Provider) => {
    setEditing(toEditing(provider));
    setDialogOpen(true);
  };

  const handleCloseDialog = (open: boolean) => {
    if (!open) {
      setDialogOpen(false);
      setEditing(undefined);
    }
  };

  const handleDelete = (provider: Provider) => {
    setItemToDelete(provider);
  };

  return (
    <div className="mx-auto max-w-4xl">
      {/* Page Header */}
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-2xl font-semibold tracking-tight text-primary">
          Providers
        </h2>
        <Button onClick={handleAdd}>
          <Plus className="mr-1 h-4 w-4" />
          Add Provider
        </Button>
      </div>

      {/* Provider List */}
      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-32 animate-pulse rounded-lg border border-border-default bg-surface-secondary"
            />
          ))}
        </div>
      ) : providers.length === 0 ? (
        <EmptyProvidersState onAdd={handleAdd} />
      ) : (
        <div className="space-y-4">
          {providers.map((provider) => (
            <ProviderCard
              key={provider.id}
              provider={provider}
              onEdit={handleEdit}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}

      <AddProviderDialog
        open={dialogOpen}
        onOpenChange={handleCloseDialog}
        editing={editing}
      />

      <DeleteConfirmDialog
        open={!!itemToDelete}
        onClose={() => setItemToDelete(null)}
        onConfirm={() => {
          if (!itemToDelete) return;
          deleteProvider.mutate(itemToDelete.id, {
            onSuccess: () => setItemToDelete(null),
          });
        }}
        isPending={deleteProvider.isPending}
        resourceName="Provider"
        itemName={itemToDelete ? itemToDelete.name : undefined}
      />
    </div>
  );
}
