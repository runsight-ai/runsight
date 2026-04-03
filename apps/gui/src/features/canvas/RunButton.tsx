import { useEffect } from "react";
import { Button } from "@runsight/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@runsight/ui/tooltip";
import { useCreateRun, useCancelRun, useRun } from "@/queries/runs";
import { useProviders } from "@/queries/settings";
import { useCanvasStore } from "@/store/canvas";
import { gitApi } from "@/api/git";
import { Play, X, Key } from "lucide-react";

interface RunButtonProps {
  workflowId: string;
  isCommitted?: boolean;
  onAddApiKey?: () => void;
}

export function RunButton({ workflowId, isCommitted = true, onAddApiKey }: RunButtonProps) {
  const activeRunId = useCanvasStore((s) => s.activeRunId);
  const setActiveRunId = useCanvasStore((s) => s.setActiveRunId);
  const nodes = useCanvasStore((s) => s.nodes);
  const blockCount = useCanvasStore((s) => s.blockCount);
  const isDirty = useCanvasStore((s) => s.isDirty);
  const yamlContent = useCanvasStore((s) => s.yamlContent);

  const { data: providers } = useProviders();
  const activeProviders = (providers?.items ?? []).filter((provider) => provider.is_active ?? true);
  const hasProviders = activeProviders.length > 0;

  const createRun = useCreateRun();
  const cancelRun = useCancelRun();

  const { data: run } = useRun(activeRunId ?? "", {
    refetchInterval: activeRunId ? 2000 : false,
  });

  const status = run?.status;
  const isRunning = activeRunId && status === "running";

  // Clear activeRunId on terminal states: completed, failed, cancelled
  useEffect(() => {
    if (activeRunId && (status === "completed" || status === "failed" || status === "cancelled")) {
      setActiveRunId(null);
    }
  }, [activeRunId, status, setActiveRunId]);

  const isEmpty = !nodes.length && !blockCount;
  const isPending = createRun.isPending || cancelRun.isPending;
  const shouldRunOnSimulation = isDirty || !isCommitted;

  async function handleClick() {
    if (isRunning) {
      cancelRun.mutate(activeRunId);
    } else if (shouldRunOnSimulation) {
      const simResult = await gitApi.createSimBranch(workflowId, yamlContent);
      createRun.mutate(
        { workflow_id: workflowId, source: "simulation", branch: simResult.branch },
        { onSuccess: (result) => setActiveRunId(result.id) },
      );
    } else {
      createRun.mutate(
        { workflow_id: workflowId, source: "manual", branch: "main" },
        { onSuccess: (result) => setActiveRunId(result.id) },
      );
    }
  }

  if (!hasProviders && !isRunning) {
    return (
      <Button
        variant="primary"
        onClick={() => onAddApiKey?.()}
      >
        <Key className="size-4" />
        Add API Key
      </Button>
    );
  }

  const button = (
    <Button
      variant={isRunning ? "danger" : "primary"}
      disabled={isEmpty && !isRunning}
      loading={isPending}
      onClick={handleClick}
    >
      {isRunning ? (
        <>
          <X className="size-4" />
          Cancel
        </>
      ) : (
        <>
          <Play className="size-4" />
          Run
        </>
      )}
    </Button>
  );

  if (isEmpty && !isRunning) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger render={button} />
          <TooltipContent>Add at least one block</TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return button;
}
