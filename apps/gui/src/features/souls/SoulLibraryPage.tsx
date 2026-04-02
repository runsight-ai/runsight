import { useNavigate } from "react-router";
import { Globe, FileText, AlertTriangle } from "lucide-react";

import { DataTable, type Column } from "@/components/shared/DataTable";
import { PageHeader } from "@/components/shared/PageHeader";
import { useSouls } from "@/queries/souls";
import { useProviders } from "@/queries/settings";
import { Badge } from "@runsight/ui/badge";
import { Button } from "@runsight/ui/button";
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

const TOOL_META: Record<
  string,
  { label: string; icon: typeof Globe }
> = {
  "runsight/http": { label: "HTTP", icon: Globe },
  "runsight/file-io": { label: "Files", icon: FileText },
};

function buildColumns(
  providerStateById: Map<string, { name: string; isActive: boolean }>,
): Column[] {
  return [
    {
      key: "role",
      header: "Name",
      sortable: true,
      render: (row) => {
        const avatarColor = row.avatar_color as string | null;
        const role = (row.role as string | null) || "Unnamed Soul";
        const soulInitial = role.trim().charAt(0).toUpperCase() || "S";
        return (
          <div className="flex items-center gap-3">
            <span
              className={`inline-flex size-6 items-center justify-center rounded-full border border-border-default text-[10px] font-semibold leading-none ${
                avatarColor
                  ? AVATAR_COLOR_CLASSES[avatarColor] ?? "bg-surface-tertiary text-primary"
                  : "bg-surface-tertiary text-primary"
              }`}
            >
              {soulInitial}
            </span>
            <span>{role}</span>
          </div>
        );
      },
    },
    {
      key: "model_name",
      header: "Model",
      sortable: true,
      render: (row) => (row.model_name as string | null) || "—",
    },
    {
      key: "provider",
      header: "Provider",
      sortable: true,
      render: (row) => {
        const providerId = row.provider as string | null;
        if (!providerId) {
          return "—";
        }

        const providerState = providerStateById.get(providerId);
        const providerLabel = providerState?.name ?? providerId;
        const isDisabled = providerState != null && !providerState.isActive;

        return (
          <div className="space-y-1">
            <div>{providerLabel}</div>
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
        const visibleTools = tools.filter((tool) => tool in TOOL_META);

        if (visibleTools.length === 0) {
          return "—";
        }

        return (
          <div className="flex flex-wrap gap-2">
            {visibleTools.map((tool) => {
              const meta = TOOL_META[tool];
              const Icon = meta.icon;
              return (
                <Badge key={tool} variant="outline" className="gap-1.5">
                  <Icon className="h-3 w-3" />
                  {meta.label}
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
      render: (row) => String(Number(row.workflow_count ?? 0)),
    },
  ];
}

export function Component() {
  const navigate = useNavigate();
  const soulsQuery = useSouls();
  const providersQuery = useProviders();
  const souls = normalizeSoulData(soulsQuery.data);
  const providerStateById = new Map(
    (providersQuery.data?.items ?? []).map((provider) => [
      provider.id,
      { name: provider.name, isActive: provider.is_active ?? true },
    ]),
  );
  const columns = buildColumns(providerStateById);

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Souls"
        subtitle={`${souls.length} soul${souls.length === 1 ? "" : "s"}`}
        actions={
          <Button onClick={() => navigate("/souls/new")}>
            New Soul
          </Button>
        }
      />

      <div className="flex-1 px-6 pb-6">
        {soulsQuery.isError ? (
          <div className="rounded-lg border border-border-default bg-surface-secondary px-4 py-6 text-sm text-muted">
            Failed to load souls.
          </div>
        ) : soulsQuery.isLoading ? (
          <div className="rounded-lg border border-border-default bg-surface-secondary px-4 py-6 text-sm text-muted">
            Loading souls...
          </div>
        ) : (
          <DataTable
            columns={columns}
            data={souls}
            sortable
            onRowClick={(row) => {
              const id = row.id;

              if (typeof id === "string" && id.length > 0) {
                navigate(`/souls/${id}/edit`);
              }
            }}
          />
        )}
      </div>
    </div>
  );
}
