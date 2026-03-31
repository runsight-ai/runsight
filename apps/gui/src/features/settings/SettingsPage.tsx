import { useState } from "react";
import { PageHeader } from "@/components/shared";
import {
  Tabs,
  TabsList,
  TabsContent,
  TabsTrigger,
} from "@runsight/ui/tabs";
import { ProvidersTab } from "./ProvidersTab";
import { ModelsTab } from "./ModelsTab";

type TabValue = "providers" | "models";

export function Component() {
  const [activeTab, setActiveTab] = useState<TabValue>("providers");

  return (
    <div className="flex h-full flex-col">
      <PageHeader title="Settings" />

      <main className="flex-1 overflow-auto bg-surface-primary p-6">
        <Tabs
          value={activeTab}
          onValueChange={(v) => setActiveTab(v as TabValue)}
          className="w-full"
        >
          <TabsList
            className="mb-6"
            aria-label="Settings sections"
            activateOnFocus={false}
          >
            <TabsTrigger value="providers">Providers</TabsTrigger>
            <TabsTrigger value="models">Models</TabsTrigger>
          </TabsList>

          <TabsContent value="providers" className="mt-0">
            <ProvidersTab />
          </TabsContent>
          <TabsContent value="models" className="mt-0">
            <ModelsTab />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
