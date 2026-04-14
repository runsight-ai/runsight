import { PageHeader } from "@/components/shared";
import {
  DEFAULT_WORKFLOW_NAME,
  buildBlankWorkflowYaml,
  deriveWorkflowId,
} from "@/features/setup/workflowDraft";
import { useCreateWorkflow } from "@/queries/workflows";
import { Button } from "@runsight/ui/button";
import type { WorkflowCreate } from "@runsight/shared/zod";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@runsight/ui/tabs";
import { Plus } from "lucide-react";
import { useNavigate } from "react-router";
import { WorkflowsTab } from "./WorkflowsTab";

function buildEmptyWorkflowCreate(): WorkflowCreate {
  const baseId = deriveWorkflowId(DEFAULT_WORKFLOW_NAME);
  const uniqueSuffix = `${Date.now().toString(36)}-${Math.random()
    .toString(36)
    .slice(2, 8)}`;
  const workflowId = `${baseId}-${uniqueSuffix}`;

  return {
    name: DEFAULT_WORKFLOW_NAME,
    yaml: buildBlankWorkflowYaml(workflowId, DEFAULT_WORKFLOW_NAME),
    canvas_state: {
      nodes: [],
      edges: [],
      viewport: { x: 0, y: 0, zoom: 1 },
      selected_node_id: null,
      canvas_mode: "dag",
    },
    commit: false,
  };
}

export function Component() {
  const navigate = useNavigate();
  const createWorkflow = useCreateWorkflow();

  const handleCreateWorkflow = () => {
    createWorkflow.mutate(buildEmptyWorkflowCreate(), {
      onSuccess: (workflow) => {
        navigate(`/workflows/${workflow.id}/edit`);
      },
    });
  };

  return (
    <div className="flex h-full flex-col bg-surface-primary">
      <PageHeader
        title="Flows"
        actions={(
          <Button
            type="button"
            onClick={handleCreateWorkflow}
            disabled={createWorkflow.isPending}
            data-testid="flows-create-workflow-button"
          >
            <Plus className="h-4 w-4" />
            New Workflow
          </Button>
        )}
      />

      <main className="flex-1 overflow-auto px-6 pb-6">
        <Tabs
          value="workflows"
          className="flex h-full flex-col"
        >
          <div className="border-b border-border-subtle">
            <TabsList aria-label="Flow sections">
              <TabsTrigger value="workflows">Workflows</TabsTrigger>
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
