import { useEffect } from "react";
import type { WorkflowSurfaceMode } from "./surfaceContract";
import { mapRunStatus } from "./surfaceUtils";

type RunNode = {
  node_id: string;
  status: string;
  cost_usd?: number | null;
  duration_seconds?: number | null;
  tokens?: { input?: number; output?: number; total?: number } | null;
  error?: string | null;
};

type UseNodeStatusMappingParams = {
  mode: WorkflowSurfaceMode;
  nodesLength: number;
  runNodes: RunNode[] | undefined;
  canvasHydrationRevision: number;
  setNodeStatus: (
    nodeId: string,
    status: ReturnType<typeof mapRunStatus>,
    meta?: {
      executionCost?: number;
      duration?: number;
      tokens?: { input?: number; output?: number; total?: number };
      error?: string | null;
    },
  ) => void;
};

export function useNodeStatusMapping({
  mode,
  nodesLength,
  runNodes,
  canvasHydrationRevision,
  setNodeStatus,
}: UseNodeStatusMappingParams): void {
  useEffect(() => {
    if (mode !== "readonly" || nodesLength === 0 || !runNodes?.length) {
      return;
    }

    for (const runNode of runNodes) {
      setNodeStatus(runNode.node_id, mapRunStatus(runNode.status), {
        executionCost: typeof runNode.cost_usd === "number" ? runNode.cost_usd : undefined,
        duration: typeof runNode.duration_seconds === "number" ? runNode.duration_seconds : undefined,
        tokens:
          runNode.tokens && typeof runNode.tokens === "object"
            ? (runNode.tokens as { input?: number; output?: number; total?: number })
            : undefined,
        error:
          typeof runNode.error === "string" || runNode.error === null ? runNode.error : undefined,
      });
    }
  }, [canvasHydrationRevision, mode, nodesLength, runNodes, setNodeStatus]);
}
