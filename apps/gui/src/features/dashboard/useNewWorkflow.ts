import { useNavigate } from "react-router";
import { useCreateWorkflow } from "@/queries/workflows";
import {
  DEFAULT_WORKFLOW_NAME,
  buildBlankWorkflowYaml,
  deriveWorkflowId,
} from "@/features/setup/workflowDraft";

export function useNewWorkflow() {
  const navigate = useNavigate();
  const createWorkflow = useCreateWorkflow();

  async function handleNewWorkflow() {
    const baseId = deriveWorkflowId(DEFAULT_WORKFLOW_NAME);
    const uniqueSuffix = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
    const workflowId = `${baseId}-${uniqueSuffix}`;
    const result = await createWorkflow.mutateAsync({
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
    });
    navigate(`/workflows/${result.id}/edit`);
  }

  return { handleNewWorkflow, isPending: createWorkflow.isPending };
}
