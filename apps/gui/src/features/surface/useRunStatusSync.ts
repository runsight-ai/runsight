import { useEffect } from "react";
import type { WorkflowSurfaceMode } from "./surfaceContract";

type Run = {
  id?: string;
  status?: string;
  total_cost_usd?: number | null;
};

type UseRunStatusSyncParams = {
  mode: WorkflowSurfaceMode;
  run: Run | null | undefined;
  setActiveCanvasRunId: (id: string | null) => void;
  setRunCost: (cost: number) => void;
};

export function useRunStatusSync({
  mode,
  run,
  setActiveCanvasRunId,
  setRunCost,
}: UseRunStatusSyncParams): void {
  useEffect(() => {
    if (mode !== "readonly" || !run) {
      setActiveCanvasRunId(null);
      return;
    }

    setRunCost(run.total_cost_usd ?? 0);
    if (run.status === "running" || run.status === "pending") {
      setActiveCanvasRunId(run.id ?? null);
      return;
    }
    setActiveCanvasRunId(null);
  }, [mode, run, setActiveCanvasRunId, setRunCost]);
}
