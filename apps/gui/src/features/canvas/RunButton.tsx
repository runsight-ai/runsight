import { useEffect } from "react";
import { Button } from "@runsight/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@runsight/ui/tooltip";
import { useCreateRun, useCancelRun, useRun } from "@/queries/runs";
import { useProviders } from "@/queries/settings";
import { useCanvasStore } from "@/store/canvas";
import { Play, X, Key } from "lucide-react";

interface RunButtonProps {
  workflowId: string;
  onAddApiKey?: () => void;
}

export function RunButton({ workflowId, onAddApiKey }: RunButtonProps) {
  const activeRunId = useCanvasStore((s) => s.activeRunId);
  const setActiveRunId = useCanvasStore((s) => s.setActiveRunId);
  const nodes = useCanvasStore((s) => s.nodes);

  const { data: providers } = useProviders();
  const items = providers?.items ?? [];
  const hasProviders = items.length > 0;

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

  const isEmpty = !nodes.length;
  const isPending = createRun.isPending || cancelRun.isPending;

  function handleClick() {
    if (isRunning) {
      cancelRun.mutate(activeRunId);
    } else {
      createRun.mutate(
        { workflow_id: workflowId, source: "manual" },
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
