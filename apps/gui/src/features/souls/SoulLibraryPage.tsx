import { useNavigate } from "react-router";

import { DataTable, type Column } from "@/components/shared/DataTable";
import { PageHeader } from "@/components/shared/PageHeader";
import { useSouls } from "@/queries/souls";
import { Button } from "@runsight/ui/button";
import type { SoulListResponse, SoulResponse } from "@runsight/shared/zod";

function normalizeSoulData(data: SoulListResponse | SoulResponse[] | undefined): SoulResponse[] {
  if (!data) {
    return [];
  }

  return Array.isArray(data) ? data : data.items;
}

const columns: Column[] = [
  {
    key: "role",
    header: "Name",
    sortable: true,
    render: (row) => (row.role as string | null) || "Unnamed Soul",
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
    render: (row) => (row.provider as string | null) || "—",
  },
  {
    key: "workflow_count",
    header: "Used In",
    sortable: true,
    sortValue: (row) => Number(row.workflow_count ?? 0),
    render: (row) => String(Number(row.workflow_count ?? 0)),
  },
];

export function Component() {
  const navigate = useNavigate();
  const soulsQuery = useSouls();
  const souls = normalizeSoulData(soulsQuery.data);

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
