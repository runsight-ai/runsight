import { PageHeader } from "@/components/shared";
import { useCreateWorkflow } from "@/queries/workflows";
import { Button } from "@runsight/ui/button";
import type { WorkflowCreate } from "@runsight/shared/zod";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@runsight/ui/tabs";
import { useState } from "react";
import { useNavigate } from "react-router";
import { WorkflowsTab } from "./WorkflowsTab";

type FlowTab = "workflows" | "runs";
const EMPTY_WORKFLOW_CREATE: WorkflowCreate = {
  canvas_state: {
    nodes: [],
    edges: [],
    viewport: { x: 0, y: 0, zoom: 1 },
    selected_node_id: null,
    canvas_mode: "dag",
  },
};

export function Component() {
  const navigate = useNavigate();
  const createWorkflow = useCreateWorkflow();
  const [activeTab, setActiveTab] = useState<FlowTab>("workflows");

  const handleCreateWorkflow = () => {
    createWorkflow.mutate(EMPTY_WORKFLOW_CREATE, {
      onSuccess: (workflow) => {
        navigate(`/workflows/${workflow.id}/edit`);
      },
    });
  };

  return (
    <div className="flex h-full flex-col bg-surface-primary">
      <PageHeader
        title="Flows"
        actions={
          <Button
            type="button"
            onClick={handleCreateWorkflow}
            disabled={createWorkflow.isPending}
          >
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
            <WorkflowsTab onCreateWorkflow={handleCreateWorkflow} />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}

export { Component as FlowsPage };
