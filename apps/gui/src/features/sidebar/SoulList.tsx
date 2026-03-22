import { useSouls, useCreateSoul, useUpdateSoul, useDeleteSoul } from "@/queries/souls";
import { CrudListPage, type CrudListPageConfig } from "@/components/shared/CrudListPage";
import { type Column } from "@/components/shared/DataTable";
import { Badge } from "@/components/ui/badge";
import { Sparkles } from "lucide-react";
import type { SoulResponse } from "@/types/schemas/souls";
import { truncateText } from "@/utils/formatting";
import { NewSoulModal, EditSoulModal } from "./SoulModals";

const columns: Column[] = [
  {
    key: "name",
    header: "Name",
    width: "1.5fr",
    render: (row) => {
      const soul = row as SoulResponse;
      return (
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-md flex items-center justify-center shrink-0 bg-[var(--primary-12)] text-[var(--primary)]">
            <Sparkles className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <div className="text-sm font-medium text-foreground truncate">{soul.name || "Unnamed Soul"}</div>
          </div>
        </div>
      );
    },
  },
  {
    key: "system_prompt",
    header: "System Prompt",
    width: "3fr",
    render: (row) => {
      const soul = row as SoulResponse;
      return (
        <div className="text-sm text-muted-foreground truncate max-w-[400px]">
          {truncateText(soul.system_prompt, 80)}
        </div>
      );
    },
  },
  {
    key: "models",
    header: "Models",
    width: "2fr",
    render: (row) => {
      const soul = row as SoulResponse;
      const models = soul.models || [];
      return (
        <div className="flex flex-wrap gap-1">
          {models.length === 0 ? (
            <span className="text-sm text-muted-foreground">—</span>
          ) : (
            models.map((model) => (
              <Badge key={model} variant="secondary" className="bg-[var(--primary-12)] text-[var(--primary)] border-none text-xs">
                {model}
              </Badge>
            ))
          )}
        </div>
      );
    },
  },
];

const soulConfig: CrudListPageConfig<SoulResponse> = {
  resourceName: "Soul",
  resourceNamePlural: "Souls",
  icon: Sparkles,
  useList: useSouls,
  useCreate: useCreateSoul,
  useUpdate: useUpdateSoul,
  useDelete: useDeleteSoul,
  columns,
  searchKeys: ["name", "system_prompt"],
  getItemName: (soul) => soul.name || "Unnamed Soul",
  getItemId: (soul) => soul.id,
  CreateModal: NewSoulModal,
  EditModal: EditSoulModal,
  emptyTitle: "No souls configured",
  emptyDescription: "Create your first soul to define AI personalities and behaviors.",
};

export function Component() {
  return <CrudListPage config={soulConfig} />;
}
