import { useState } from "react";
import {
  useProviders,
  useDeleteProvider,
  useTestProviderConnection,
  useUpdateProvider,
} from "@/queries/settings";
import { DeleteConfirmDialog } from "@/components/shared";
import { BadgeDot } from "@runsight/ui/badge";
import { EmptyState } from "@runsight/ui/empty-state";
import { Button } from "@runsight/ui/button";
import { Skeleton } from "@runsight/ui/skeleton";
import { Switch } from "@runsight/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableMonoCell,
  TableRow,
} from "@runsight/ui/table";
import { Server, AlertCircle, RotateCcw } from "lucide-react";
import { AddProviderDialog } from "./AddProviderDialog";
import type { EditingProvider } from "@/components/provider/ProviderSetup";
import { cn } from "@runsight/ui/utils";
import type { Provider } from "@/api/settings";
import type { CSSProperties } from "react";

const PROVIDER_LOGO_TONES = [
  {
    backgroundColor: "var(--neutral-6)",
    borderColor: "var(--neutral-6)",
    color: "var(--text-primary)",
  },
  {
    backgroundColor: "var(--accent-8)",
    borderColor: "var(--accent-8)",
    color: "var(--text-on-accent)",
  },
  {
    backgroundColor: "var(--info-9)",
    borderColor: "var(--info-9)",
    color: "var(--text-on-accent)",
  },
  {
    backgroundColor: "var(--success-9)",
    borderColor: "var(--success-9)",
    color: "var(--text-on-accent)",
  },
  {
    backgroundColor: "var(--warning-9)",
    borderColor: "var(--warning-9)",
    color: "var(--warning-11)",
  },
  {
    backgroundColor: "var(--danger-9)",
    borderColor: "var(--danger-9)",
    color: "var(--text-on-accent)",
  },
] as const;

function getProviderInitials(name: string) {
  return name
    .split(/\s+/)
    .map((word) => word[0])
    .join("")
    .toUpperCase()
    .slice(0, 3);
}

function getProviderLogoTone(name: string): CSSProperties {
  const normalized = name.trim().toLowerCase();
  if (normalized === "anthropic") {
    return PROVIDER_LOGO_TONES[1];
  }
  if (normalized === "openai") {
    return PROVIDER_LOGO_TONES[0];
  }

  const hash = [...normalized].reduce(
    (acc, char) => acc + char.charCodeAt(0),
    0,
  );
  return PROVIDER_LOGO_TONES[hash % PROVIDER_LOGO_TONES.length];
}

function ProviderLogo({ name }: { name: string }) {

  return (
    <div
      style={getProviderLogoTone(name)}
      className={cn(
        "flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full border",
      )}
    >
      <span className="text-xs font-semibold">{getProviderInitials(name)}</span>
    </div>
  );
}

function getStatusDotClass(status: string): string {
  switch (status) {
    case "connected":
    case "active":
      return "text-success-9";
    case "rate-limited":
      return "text-warning-9";
    case "error":
      return "text-danger-9";
    default:
      return "text-neutral-9";
  }
}

function getStatusLabel(status: string): string {
  switch (status) {
    case "connected":
    case "active":
      return "Connected";
    case "rate-limited":
      return "Rate limited";
    case "error":
      return "Error";
    case "offline":
      return "Offline";
    default:
      return "Unknown";
  }
}

function ProviderRow({
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
  const [testStatus, setTestStatus] = useState<"idle" | "testing">("idle");

  const handleTest = async () => {
    setTestStatus("testing");
    try {
      await testConnection.mutateAsync(provider.id);
    } catch {
      // surfaced by toast and refreshed provider status
    } finally {
      setTestStatus("idle");
    }
  };

  const handleToggle = (enabled: boolean) => {
    updateProvider.mutate({
      id: provider.id,
      data: { name: provider.name, is_active: enabled },
    });
  };

  const isEnabled = provider.is_active ?? true;
  const keyPreview = provider.api_key_preview
    ? provider.api_key_preview
    : provider.api_key_env?.startsWith("$")
      ? `Configured via ${provider.api_key_env}`
      : "(none configured)";

  return (
    <TableRow>
      <TableCell className="border-b-0 py-3">
        <div className="flex items-center gap-2.5">
          <ProviderLogo name={provider.name} />
          <div className="min-w-0">
            <div className="text-md font-medium text-heading">{provider.name}</div>
            {provider.base_url ? (
              <div className="truncate text-xs text-muted">{provider.base_url}</div>
            ) : null}
          </div>
        </div>
      </TableCell>
      <TableMonoCell className="border-b-0 py-3 text-secondary">{keyPreview}</TableMonoCell>
      <TableCell className="border-b-0 py-3">
        <div
          aria-label={`Provider ${provider.name} status ${getStatusLabel(provider.status)}`}
          className="inline-flex items-center gap-1.5 text-sm text-secondary"
        >
          <BadgeDot className={getStatusDotClass(provider.status)} />
          <span>{getStatusLabel(provider.status)}</span>
        </div>
      </TableCell>
      <TableCell className="border-b-0 py-3 text-sm text-secondary">
        {(provider.models?.length || 0) === 1
          ? "1 model"
          : `${provider.models?.length || 0} models`}
      </TableCell>
      <TableCell className="w-[1%] border-b-0 py-3 whitespace-nowrap">
        <div className="flex items-center gap-1.5">
          <Switch
            checked={isEnabled}
            onCheckedChange={handleToggle}
            aria-label={`Enable ${provider.name} provider`}
            wrapperClassName="mr-1"
            className="scale-90"
          />
          <Button
            variant="ghost"
            size="xs"
            onClick={handleTest}
            disabled={testStatus === "testing"}
            className="px-1.5 text-secondary"
            aria-label={`Test ${provider.name} connection`}
          >
            {testStatus === "testing" ? "Testing..." : "Test"}
          </Button>
          <Button
            variant="ghost"
            size="xs"
            onClick={() => onEdit(provider)}
            className="px-1.5 text-secondary"
            aria-label={`Edit ${provider.name} provider`}
          >
            Edit
          </Button>
          <Button
            variant="ghost"
            size="xs"
            onClick={() => onDelete(provider)}
            className="text-[var(--danger-11)] hover:bg-[var(--danger-3)] hover:text-[var(--danger-11)]"
            aria-label={`Delete ${provider.name} provider`}
          >
            Delete
          </Button>
        </div>
      </TableCell>
    </TableRow>
  );
}

function ProviderTableSkeleton() {
  return (
    <div>
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead>Provider</TableHead>
            <TableHead>API Key</TableHead>
            <TableHead className="w-[140px]">Status</TableHead>
            <TableHead className="w-[140px]">Models</TableHead>
            <TableHead className="w-[220px] text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {[1, 2, 3].map((index) => (
            <TableRow key={index}>
              <TableCell colSpan={5}>
                <div className="flex items-center gap-4 py-2">
                  <Skeleton variant="avatar" className="h-7 w-7 rounded-full" />
                  <div className="grid flex-1 grid-cols-[1.1fr_1fr_140px_120px_180px] gap-4">
                    <Skeleton className="w-36" />
                    <Skeleton className="w-40" />
                    <Skeleton className="w-24" />
                    <Skeleton className="w-20" />
                    <Skeleton variant="button" className="w-24" />
                  </div>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

interface ProvidersTabProps {
  onAddProvider: () => void;
  onEditProvider: (provider: Provider) => void;
  dialogOpen: boolean;
  onDialogOpenChange: (open: boolean) => void;
  editing?: EditingProvider;
}

export function ProvidersTab({
  onAddProvider,
  onEditProvider,
  dialogOpen,
  onDialogOpenChange,
  editing,
}: ProvidersTabProps) {
  const { data, isLoading, error, refetch } = useProviders();
  const deleteProvider = useDeleteProvider();
  const [itemToDelete, setItemToDelete] = useState<Provider | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);

  const providers = data?.items || [];

  const handleDelete = (provider: Provider) => {
    setItemToDelete(provider);
  };

  const handleRetry = async () => {
    setIsRetrying(true);
    try {
      await refetch();
    } finally {
      setIsRetrying(false);
    }
  };

  return (
    <div className="w-full">
      {isLoading ? (
        <ProviderTableSkeleton />
      ) : error ? (
        <div className="flex items-center justify-center rounded-lg border border-border-default bg-surface-secondary p-8">
          <div className="max-w-md text-center">
            <AlertCircle className="mx-auto mb-4 h-12 w-12 text-danger" />
            <h3 className="mb-2 text-lg font-medium text-primary">
              Failed to load providers
            </h3>
            <p className="mb-4 text-sm text-muted">
              {error instanceof Error
                ? error.message
                : "An error occurred while fetching providers."}
            </p>
            <Button
              onClick={handleRetry}
              variant="secondary"
              disabled={isRetrying}
            >
              <RotateCcw className="mr-2 h-4 w-4" />
              {isRetrying ? "Retrying..." : "Retry"}
            </Button>
          </div>
        </div>
      ) : providers.length === 0 ? (
        <div className="rounded-lg border border-border-default bg-surface-primary p-8">
          <EmptyState
            icon={Server}
            title="No providers configured"
            description="Add an AI provider to start using Runsight with models like GPT-4, Claude, or local Ollama instances."
            action={{ label: "Add Provider", onClick: onAddProvider }}
          />
        </div>
      ) : (
        <div>
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Provider</TableHead>
                <TableHead>API Key</TableHead>
                <TableHead className="w-[140px]">Status</TableHead>
                <TableHead className="w-[140px]">Models</TableHead>
                <TableHead className="w-[220px]">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {providers.map((provider) => (
                <ProviderRow
                  key={provider.id}
                  provider={provider}
                  onEdit={onEditProvider}
                  onDelete={handleDelete}
                />
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <AddProviderDialog
        open={dialogOpen}
        onOpenChange={onDialogOpenChange}
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
