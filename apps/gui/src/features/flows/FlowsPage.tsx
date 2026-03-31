import { PageHeader } from "@/components/shared";
import { Button } from "@runsight/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@runsight/ui/tabs";
import { Suspense, lazy, useState } from "react";
import { WorkflowsTab } from "./WorkflowsTab";

type FlowTab = "workflows" | "runs";
const NewWorkflowModal = lazy(() =>
  import("../workflows/NewWorkflowModal").then((module) => ({
    default: module.NewWorkflowModal,
  })),
);

export function Component() {
  const [activeTab, setActiveTab] = useState<FlowTab>("workflows");
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  return (
    <div className="flex h-full flex-col bg-surface-primary">
      <PageHeader
        title="Flows"
        actions={
          <Button type="button" onClick={() => setIsCreateModalOpen(true)}>
            New Workflow
          </Button>
        }
      />

      <main className="flex-1 overflow-auto px-6 pb-6">
        <Tabs
          value={activeTab}
          onValueChange={(value) => setActiveTab(value as FlowTab)}
          className="flex h-full flex-col"
        >
          <div className="border-b border-border-subtle">
            <TabsList aria-label="Flow sections">
              <TabsTrigger value="workflows">Workflows</TabsTrigger>
              <TabsTrigger value="runs" disabled>
                <span>Runs</span>
                <span className="text-xs text-muted">Coming soon</span>
              </TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="workflows" className="mt-0 flex-1">
            <WorkflowsTab onCreateWorkflow={() => setIsCreateModalOpen(true)} />
          </TabsContent>
        </Tabs>
      </main>

      {isCreateModalOpen ? (
        <Suspense fallback={null}>
          <NewWorkflowModal
            open={isCreateModalOpen}
            onClose={() => setIsCreateModalOpen(false)}
          />
        </Suspense>
      ) : null}
    </div>
  );
}

export { Component as FlowsPage };
