import { useSouls, useDeleteSoul } from "@/queries/souls";
import { CrudListPage, type CrudListPageConfig } from "@/components/shared/CrudListPage";
import { type Column } from "@/components/shared/DataTable";
import { Badge } from "@runsight/ui/badge";
import { Sparkles } from "lucide-react";
import type { SoulResponse } from "@runsight/shared/zod";
import { truncateText } from "@/utils/formatting";
import { NewSoulModal, EditSoulModal } from "./SoulModals";

const columns: Column[] = [
  {
    key: "role",
    header: "Role",
    width: "1.5fr",
    render: (row) => {
      const soul = row as SoulResponse;
      return (
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-md flex items-center justify-center shrink-0 bg-[var(--accent-3)] text-[var(--interactive-default)]">
            <Sparkles className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <div className="text-sm font-medium text-primary truncate">{soul.role || "Unnamed Soul"}</div>
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
        <div className="text-sm text-muted truncate max-w-[400px]">
          {truncateText(soul.system_prompt, 80)}
        </div>
      );
    },
  },
  {
    key: "model_name",
    header: "Model",
    width: "2fr",
    render: (row) => {
      const soul = row as SoulResponse;
      const modelName = soul.model_name;
      return (
        <div className="flex flex-wrap gap-1">
          {!modelName ? (
            <span className="text-sm text-muted">—</span>
          ) : (
            <Badge variant="neutral" className="bg-[var(--accent-3)] text-[var(--interactive-default)] border-none text-xs">
              {modelName}
            </Badge>
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
  useDelete: useDeleteSoul,
  columns,
  searchKeys: ["role", "system_prompt"],
  getItemName: (soul) => soul.role || "Unnamed Soul",
  getItemId: (soul) => soul.id,
  CreateModal: NewSoulModal,
  EditModal: EditSoulModal,
  emptyTitle: "No souls configured",
  emptyDescription: "Create your first soul to define AI personalities and behaviors.",
};

export function Component() {
  return <CrudListPage config={soulConfig} />;
}
