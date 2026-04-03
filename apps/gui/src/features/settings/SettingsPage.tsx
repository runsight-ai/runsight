import { useState } from "react";
import { PageHeader } from "@/components/shared";
import { Button } from "@runsight/ui/button";
import {
  Tabs,
  TabsList,
  TabsContent,
  TabsTrigger,
} from "@runsight/ui/tabs";
import { Plus } from "lucide-react";
import { ProvidersTab } from "./ProvidersTab";
import { ModelsTab } from "./ModelsTab";
import type { EditingProvider } from "@/components/provider/ProviderSetup";
import type { Provider } from "@/api/settings";

type TabValue = "providers" | "fallback";

function toEditing(provider: Provider): EditingProvider {
  return {
    id: provider.id,
    name: provider.name,
    type: provider.name.toLowerCase().replace(/\s+/g, "_"),
    baseUrl: provider.base_url,
    hasKey: !!provider.api_key_env,
  };
}

export function Component() {
  const [activeTab, setActiveTab] = useState<TabValue>("providers");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<EditingProvider | undefined>(undefined);

  const handleAddProvider = () => {
    setEditing(undefined);
    setDialogOpen(true);
  };

  const handleEditProvider = (provider: Provider) => {
    setEditing(toEditing(provider));
    setDialogOpen(true);
  };

  const handleDialogOpenChange = (open: boolean) => {
    setDialogOpen(open);
    if (!open) {
      setEditing(undefined);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Settings"
        actions={
          activeTab === "providers" ? (
            <Button size="sm" onClick={handleAddProvider}>
              <Plus className="h-3.5 w-3.5" />
              Add Provider
            </Button>
          ) : null
        }
      />

      <main className="flex-1 overflow-auto bg-surface-primary px-6 pb-6">
        <Tabs
          value={activeTab}
          onValueChange={(v) => setActiveTab(v as TabValue)}
          className="flex h-full w-full flex-col"
        >
          <TabsList
            className="mb-6"
            aria-label="Settings sections"
            activateOnFocus={false}
          >
            <TabsTrigger value="providers">Providers</TabsTrigger>
            <TabsTrigger value="fallback">Fallback</TabsTrigger>
          </TabsList>

          <TabsContent value="providers" className="mt-0">
            <ProvidersTab
              onAddProvider={handleAddProvider}
              onEditProvider={handleEditProvider}
              dialogOpen={dialogOpen}
              onDialogOpenChange={handleDialogOpenChange}
              editing={editing}
            />
          </TabsContent>
          <TabsContent value="fallback" className="mt-0">
            <ModelsTab />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
