import { useNavigate } from "react-router";
import { useCreateWorkflow } from "@/queries/workflows";
import { buildBlankWorkflowCreate } from "@/features/setup/workflowDraft";

export function useNewWorkflow() {
  const navigate = useNavigate();
  const createWorkflow = useCreateWorkflow();

  async function handleNewWorkflow() {
    const result = await createWorkflow.mutateAsync(buildBlankWorkflowCreate());
    navigate(`/workflows/${result.id}/edit`);
  }

  return { handleNewWorkflow, isPending: createWorkflow.isPending };
}
