import { PageHeader } from "@/components/shared";
import { useCreateWorkflow } from "@/queries/workflows";
import { Button } from "@runsight/ui/button";
import type { WorkflowCreate } from "@runsight/shared/zod";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@runsight/ui/tabs";
import { useNavigate, useSearchParams } from "react-router";
import { RunsTab } from "./RunsTab";
import { WorkflowsTab } from "./WorkflowsTab";

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
  const [searchParams, setSearchParams] = useSearchParams();
  const createWorkflow = useCreateWorkflow();
  const activeTab = searchParams.get("tab") === "runs" ? "runs" : "workflows";

  const handleCreateWorkflow = () => {
    createWorkflow.mutate(EMPTY_WORKFLOW_CREATE, {
      onSuccess: (workflow) => {
        navigate(`/workflows/${workflow.id}/edit`);
      },
    });
  };

  const handleTabChange = (value: string) => {
    const nextTab = value === "runs" ? "runs" : "workflows";
    const nextSearchParams = new URLSearchParams(searchParams);

    if (nextTab === "runs") {
      nextSearchParams.set("tab", "runs");
    } else {
      nextSearchParams.delete("tab");
    }

    setSearchParams(nextSearchParams);
  };

  return (
    <div className="flex h-full flex-col bg-surface-primary">
      <PageHeader
        title="Flows"
        actions={activeTab === "workflows" ? (
          <Button
            type="button"
            onClick={handleCreateWorkflow}
            disabled={createWorkflow.isPending}
          >
            New Workflow
          </Button>
        ) : undefined}
      />

      <main className="flex-1 overflow-auto px-6 pb-6">
        <Tabs
          value={activeTab}
          onValueChange={handleTabChange}
          className="flex h-full flex-col"
        >
          <div className="border-b border-border-subtle">
            <TabsList aria-label="Flow sections">
              <TabsTrigger value="workflows">Workflows</TabsTrigger>
              <TabsTrigger value="runs">Runs</TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="workflows" className="mt-0 flex-1">
            <WorkflowsTab onCreateWorkflow={handleCreateWorkflow} />
          </TabsContent>
          <TabsContent value="runs" className="mt-0 flex-1">
            <RunsTab onGoToWorkflows={() => handleTabChange("workflows")} />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}

export { Component as FlowsPage };
