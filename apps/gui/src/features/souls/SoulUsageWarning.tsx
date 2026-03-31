import type { SoulUsageResponse } from "@runsight/shared/zod";
import { Badge } from "@runsight/ui/badge";
import { AlertTriangle, Loader2 } from "lucide-react";

interface SoulUsageWarningProps {
  isLoading: boolean;
  isError: boolean;
  errorMessage?: string;
  usageData?: SoulUsageResponse;
}

export function SoulUsageWarning({
  isLoading,
  isError,
  errorMessage,
  usageData,
}: SoulUsageWarningProps) {
  if (isLoading) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-border-default bg-surface-secondary px-3 py-3 text-sm text-muted">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span>Checking workflow usage…</span>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-lg border border-warning/30 bg-surface-secondary px-3 py-3 text-sm text-muted">
        <div className="flex items-center gap-2 text-primary">
          <AlertTriangle className="h-4 w-4" />
          <span>Could not check workflow usage</span>
        </div>
        {errorMessage ? <p className="mt-2">{errorMessage}</p> : null}
      </div>
    );
  }

  const usages = usageData?.usages ?? [];
  const total = usageData?.total ?? 0;

  if (total === 0) {
    return null;
  }

  const visibleUsages = usages.slice(0, 5);
  const remainingCount = total - visibleUsages.length;

  return (
    <div className="rounded-lg border border-warning/30 bg-surface-secondary px-3 py-3 text-sm text-muted">
      <div className="flex items-center gap-2 text-primary">
        <AlertTriangle className="h-4 w-4" />
        <span>This soul is currently used in active workflows.</span>
      </div>
      <div className="mt-3 text-sm font-medium text-primary">{total} workflows</div>
      <div className="mt-3 flex flex-wrap gap-2">
        {visibleUsages.map((usage) => (
          <Badge
            key={usage.workflow_id}
            variant="neutral"
            className="bg-surface-primary"
          >
            {usage.workflow_name}
          </Badge>
        ))}
        {remainingCount > 0 ? (
          <Badge variant="outline">
            +{remainingCount} more
          </Badge>
        ) : null}
      </div>
    </div>
  );
}
