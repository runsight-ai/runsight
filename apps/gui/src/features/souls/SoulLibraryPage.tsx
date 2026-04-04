import { useNavigate } from "react-router";
import { AlertTriangle, Bot, Plus } from "lucide-react";

import { DataTable, type Column } from "@/components/shared/DataTable";
import { PageHeader } from "@/components/shared/PageHeader";
import { useAvailableTools, useSouls } from "@/queries/souls";
import { useProviders } from "@/queries/settings";
import { Badge } from "@runsight/ui/badge";
import { Button } from "@runsight/ui/button";
import { EmptyState } from "@runsight/ui/empty-state";
import { Skeleton } from "@runsight/ui/skeleton";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@runsight/ui/tooltip";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@runsight/ui/table";
import type { SoulListResponse, SoulResponse } from "@runsight/shared/zod";

function normalizeSoulData(data: SoulListResponse | SoulResponse[] | undefined): SoulResponse[] {
  if (!data) {
    return [];
  }

  return Array.isArray(data) ? data : data.items;
}

const AVATAR_COLOR_CLASSES: Record<string, string> = {
  accent: "bg-accent-8 text-on-accent",
  info: "bg-info-9 text-on-accent",
  success: "bg-success-9 text-on-accent",
  warning: "bg-warning-9 text-on-accent",
  danger: "bg-danger-9 text-on-accent",
  neutral: "bg-neutral-8 text-on-accent",
};

type AvailableTool = {
  id: string;
  name: string;
  description: string;
  origin: string;
  executor: string;
};

function formatMetadataLabel(value: string, kind: "origin" | "executor"): string {
  const normalized = value.trim().toLowerCase();

  if (kind === "origin") {
    if (normalized === "builtin") {
      return "Built-in";
    }
    if (normalized === "custom") {
      return "Custom";
    }
  }

  if (kind === "executor") {
    if (normalized === "native") {
      return "Native";
    }
    if (normalized === "python") {
      return "Python";
    }
    if (normalized === "request") {
      return "Request";
    }
  }

  return value
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatWorkflowCount(count: number) {
  return `${count} workflow${count === 1 ? "" : "s"}`;
}

function formatRelativeTime(timestamp: number | null | undefined) {
  if (!timestamp) {
    return "—";
  }

  const secondsAgo = Math.max(0, Math.floor(Date.now() / 1000 - timestamp));

  if (secondsAgo < 60) {
    return "just now";
  }

  const minutesAgo = Math.floor(secondsAgo / 60);
  if (minutesAgo < 60) {
    return `${minutesAgo}m ago`;
  }

  const hoursAgo = Math.floor(minutesAgo / 60);
  if (hoursAgo < 24) {
    return `${hoursAgo}h ago`;
  }

  const daysAgo = Math.floor(hoursAgo / 24);
  return `${daysAgo}d ago`;
}

function buildColumns(
  providerStateById: Map<string, { name: string; isActive: boolean }>,
  toolMetaById: Map<string, AvailableTool>,
): Column[] {
  return [
    {
      key: "role",
      header: "Name",
      sortable: true,
      render: (row) => {
        const avatarColor = row.avatar_color as string | null;
        const role = (row.role as string | null) || "Unnamed Soul";
        const hasPromptWarning = !String(row.system_prompt ?? "").trim();
        const soulInitial = role.trim().charAt(0).toUpperCase() || "S";
        return (
          <div className="flex items-center gap-3.5">
            <span
              className={`inline-flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold leading-none ${
                avatarColor
                  ? AVATAR_COLOR_CLASSES[avatarColor] ?? "bg-surface-secondary text-primary"
                  : "bg-surface-secondary text-primary"
              }`}
            >
              {soulInitial}
            </span>
            <span className="inline-flex items-center gap-1.5 font-semibold text-heading">
              <span>{role}</span>
              {hasPromptWarning ? (
                <TooltipProvider delay={200}>
                  <Tooltip>
                    <TooltipTrigger
                      render={
                        <span
                          className="inline-flex items-center"
                          aria-label="Soul prompt warning"
                        >
                          <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-warning-9" />
                        </span>
                      }
                    />
                    <TooltipContent className="max-w-[320px] whitespace-normal px-3 py-3">
                      <div className="flex items-start gap-2.5">
                        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning-9" />
                        <div className="min-w-0">
                          <div className="text-md font-medium text-primary">
                            Missing system prompt
                          </div>
                          <div className="mt-1 text-sm leading-5 text-secondary">
                            This soul is incomplete for workflow use. Add a prompt before
                            assigning it to a workflow.
                          </div>
                        </div>
                      </div>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              ) : null}
            </span>
          </div>
        );
      },
    },
    {
      key: "model_name",
      header: "Model",
      sortable: true,
      render: (row) => (
        <span className="font-mono text-sm text-muted">
          {(row.model_name as string | null) || "—"}
        </span>
      ),
    },
    {
      key: "provider",
      header: "Provider",
      sortable: true,
      render: (row) => {
        const providerId = row.provider as string | null;
        if (!providerId) {
          return <span className="text-muted">—</span>;
        }

        const providerState = providerStateById.get(providerId);
        const providerLabel = providerState?.name ?? providerId;
        const isDisabled = providerState != null && !providerState.isActive;

        return (
          <div className="space-y-1">
            <div className="text-secondary">{providerLabel}</div>
            {isDisabled ? (
              <div className="flex items-center gap-1.5 text-xs text-warning-11">
                <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-warning-9" />
                <span>Provider disabled</span>
              </div>
            ) : null}
          </div>
        );
      },
    },
    {
      key: "tools",
      header: "Tools",
      sortable: false,
      render: (row) => {
        const tools = Array.isArray(row.tools) ? (row.tools as string[]) : [];
        const visibleTools = tools.filter((toolId) => toolId !== "delegate");

        if (visibleTools.length === 0) {
          return <span className="text-muted">—</span>;
        }

        return (
          <div className="flex flex-wrap gap-1.5">
            {visibleTools.map((toolId) => {
              const meta = toolMetaById.get(toolId);
              const metadataLabels = [
                ...(meta?.origin && meta.origin !== "builtin"
                  ? [formatMetadataLabel(meta.origin, "origin")]
                  : []),
                ...(meta?.executor && meta.executor !== "native"
                  ? [formatMetadataLabel(meta.executor, "executor")]
                  : []),
              ];

              return (
                <Badge
                  key={toolId}
                  variant="outline"
                  className="gap-1.5 border-border-subtle bg-surface-secondary text-secondary"
                >
                  <span>{meta?.name ?? toolId}</span>
                  {metadataLabels.length > 0 ? (
                    <span className="text-muted">{metadataLabels.join(" / ")}</span>
                  ) : null}
                </Badge>
              );
            })}
          </div>
        );
      },
    },
    {
      key: "workflow_count",
      header: "Used In",
      sortable: true,
      sortValue: (row) => Number(row.workflow_count ?? 0),
      render: (row) => {
        const workflowCount = Number(row.workflow_count ?? 0);
        return <span className="text-secondary">{formatWorkflowCount(workflowCount)}</span>;
      },
    },
    {
      key: "modified_at",
      header: "Modified",
      sortable: true,
      sortValue: (row) => Number(row.modified_at ?? 0),
      render: (row) => (
        <span className="text-muted">
          {formatRelativeTime(row.modified_at as number | null | undefined)}
        </span>
      ),
    },
  ];
}

function SoulTableSkeleton() {
  return (
    <div className="flex flex-col gap-3">
      <Skeleton className="h-8 w-full rounded-md" />
      <Table>
        <TableHeader>
          <TableRow className="border-b border-border-subtle hover:bg-transparent">
            {["Name", "Model", "Provider", "Tools", "Used In", "Modified"].map((header) => (
              <TableHead key={header} className="h-9 px-2.5 border-b-0">
                {header}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {Array.from({ length: 3 }).map((_, index) => (
            <TableRow key={index} className="h-[var(--control-height-lg)] hover:bg-transparent">
              <TableCell className="border-b-0 px-2.5 py-0">
                <div className="flex items-center gap-3.5">
                  <Skeleton variant="avatar" className="size-7" />
                  <Skeleton className="h-4 w-28" />
                </div>
              </TableCell>
              <TableCell className="border-b-0 px-2.5 py-0">
                <Skeleton className="h-4 w-20" />
              </TableCell>
              <TableCell className="border-b-0 px-2.5 py-0">
                <Skeleton className="h-4 w-24" />
              </TableCell>
              <TableCell className="border-b-0 px-2.5 py-0">
                <div className="flex gap-2">
                  <Skeleton className="h-5 w-16 rounded-full" />
                  <Skeleton className="h-5 w-14 rounded-full" />
                </div>
              </TableCell>
              <TableCell className="border-b-0 px-2.5 py-0">
                <Skeleton className="h-4 w-20" />
              </TableCell>
              <TableCell className="border-b-0 px-2.5 py-0">
                <Skeleton className="h-4 w-16" />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export function Component() {
  const navigate = useNavigate();
  const soulsQuery = useSouls();
  const availableToolsQuery = useAvailableTools();
  const providersQuery = useProviders();
  const souls = normalizeSoulData(soulsQuery.data);
  const providerStateById = new Map(
    (providersQuery.data?.items ?? []).map((provider) => [
      provider.id,
      { name: provider.name, isActive: provider.is_active ?? true },
    ]),
  );
  const toolMetaById = new Map(
    (availableToolsQuery.data ?? [])
      .filter((tool) => tool.id !== "delegate")
      .map((tool) => [tool.id, tool]),
  );
  const columns = buildColumns(providerStateById, toolMetaById);

  return (
    <div className="flex h-full flex-col bg-surface-primary">
      <PageHeader
        title="Souls"
        actions={(
          <Button onClick={() => navigate("/souls/new")}>
            <Plus className="h-4 w-4" />
            New Soul
          </Button>
        )}
      />

      <main className="flex-1 overflow-auto px-6 pb-6">
        {soulsQuery.isError ? (
          <EmptyState
            icon={AlertTriangle}
            title="Couldn't load souls"
            description="Check file permissions on the custom/souls/ directory."
            action={{ label: "Retry", onClick: () => void soulsQuery.refetch() }}
            className="min-h-[320px]"
          />
        ) : soulsQuery.isLoading ? (
          <SoulTableSkeleton />
        ) : (
          <DataTable
            columns={columns}
            data={souls}
            searchable
            sortable
            variant="minimal"
            searchPlaceholder="Search souls..."
            emptyState={
              <EmptyState
                icon={Bot}
                title="No souls yet"
                description="Souls define your AI agents: their role, model, and behavior. Create one to use in your workflows."
                action={{ label: "Create Your First Soul", onClick: () => navigate("/souls/new") }}
                className="min-h-[320px]"
              />
            }
            onRowClick={(row) => {
              const id = row.id;

              if (typeof id === "string" && id.length > 0) {
                navigate(`/souls/${id}/edit`);
              }
            }}
          />
        )}
      </main>
    </div>
  );
}
