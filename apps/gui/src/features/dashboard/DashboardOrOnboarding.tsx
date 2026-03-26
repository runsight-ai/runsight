import { useNavigate } from "react-router";
import { Plus } from "lucide-react";
import { PageHeader } from "@/components/shared/PageHeader";
import { Button } from "@/components/ui/button";
import { useCreateWorkflow } from "@/queries/workflows";

export function Component() {
  const navigate = useNavigate();
  const createWorkflow = useCreateWorkflow();

  async function handleNewWorkflow() {
    const result = await createWorkflow.mutateAsync({});
    navigate(`/workflows/${result.id}/edit`);
  }

  return (
    <div className="flex-1 flex flex-col">
      <PageHeader
        title="Home"
        actions={
          <Button onClick={handleNewWorkflow} disabled={createWorkflow.isPending}>
            <Plus className="w-4 h-4 mr-2" />
            New Workflow
          </Button>
        }
      />
      <div className="flex-1" />
    </div>
  );
}
