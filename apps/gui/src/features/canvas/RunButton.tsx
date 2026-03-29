import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { useCreateRun, useCancelRun, useRun } from "@/queries/runs";
import { useCanvasStore } from "@/store/canvas";
import { Play, X } from "lucide-react";

interface RunButtonProps {
  workflowId: string;
}

export function RunButton({ workflowId }: RunButtonProps) {
  const activeRunId = useCanvasStore((s) => s.activeRunId);
  const setActiveRunId = useCanvasStore((s) => s.setActiveRunId);
  const nodes = useCanvasStore((s) => s.nodes);

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
    return <Tooltip content="Add at least one block">{button}</Tooltip>;
  }

  return button;
}
