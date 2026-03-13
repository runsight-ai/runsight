import { useState } from "react";
import { PageHeader } from "@/components/shared";
import {
  Tabs,
  TabsContent,
} from "@/components/ui/tabs";
import {
  Plug,
  Bot,
  Wallet,
  User,
  Settings,
} from "lucide-react";
import { ProvidersTab } from "./ProvidersTab";
import { ModelsTab } from "./ModelsTab";
import { BudgetsTab } from "./BudgetsTab";
import { cn } from "@/utils/helpers";

type TabValue = "providers" | "models" | "budgets";

const settingsNavItems = [
  { value: "providers" as TabValue, label: "Providers", icon: Plug },
  { value: "models" as TabValue, label: "Models", icon: Bot },
  { value: "budgets" as TabValue, label: "Budgets", icon: Wallet },
  { value: "profile" as const, label: "Profile", icon: User },
  { value: "advanced" as const, label: "Advanced", icon: Settings },
];

export function Component() {
  const [activeTab, setActiveTab] = useState<TabValue>("providers");

  return (
    <div className="flex h-full flex-col">
      {/* Header Bar (48px) */}
      <PageHeader
        title="Global Settings"
        backHref="/"
      />

      {/* Settings Layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Settings Nav Sidebar (200px) */}
        <aside className="w-[200px] flex-shrink-0 border-r border-border bg-card p-3">
          <nav className="space-y-0.5">
            {settingsNavItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.value;
              const isImplemented = ["providers", "models", "budgets"].includes(
                item.value
              );

              return (
                <button
                  key={item.value}
                  onClick={() =>
                    isImplemented && setActiveTab(item.value as TabValue)
                  }
                  className={cn(
                    "flex h-9 w-full items-center gap-3 rounded-md px-3 text-sm transition-colors relative",
                    isActive
                      ? "text-foreground"
                      : "text-muted-foreground hover:bg-accent hover:text-foreground",
                    !isImplemented && "opacity-50 cursor-not-allowed"
                  )}
                >
                  {isActive && (
                    <span className="absolute left-0 top-2 bottom-2 w-0.5 bg-primary rounded-full" />
                  )}
                  <Icon className="h-4 w-4" />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>
        </aside>

        {/* Main Content */}
        <main className="flex-1 overflow-auto bg-background p-6">
          <Tabs
            value={activeTab}
            onValueChange={(v) => setActiveTab(v as TabValue)}
            className="w-full"
          >
            <TabsContent value="providers" className="mt-0">
              <ProvidersTab />
            </TabsContent>
            <TabsContent value="models" className="mt-0">
              <ModelsTab />
            </TabsContent>
            <TabsContent value="budgets" className="mt-0">
              <BudgetsTab />
            </TabsContent>
          </Tabs>
        </main>
      </div>
    </div>
  );
}
