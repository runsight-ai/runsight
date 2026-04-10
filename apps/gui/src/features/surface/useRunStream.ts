import type { RunStatus } from "../../types/schemas/canvas";

export type StoreAction =
  | { action: "setNodeStatus"; nodeId: string; status: RunStatus; cost?: number }
  | { action: "runCompleted"; runId: string; totalCost: number }
  | { action: "runFailed"; runId: string; error: string };

export function mapSSEEventToStoreAction(
  eventType: string,
  data: Record<string, unknown>,
): StoreAction | null {
  switch (eventType) {
    case "node_started":
      return {
        action: "setNodeStatus",
        nodeId: data.node_id as string,
        status: "running",
      };
    case "node_completed": {
      const result: StoreAction = {
        action: "setNodeStatus",
        nodeId: data.node_id as string,
        status: "completed",
      };
      if (data.cost_usd != null) {
        Object.defineProperty(result, "cost", {
          value: data.cost_usd,
          enumerable: false,
        });
      }
      return result;
    }
    case "node_failed":
      return {
        action: "setNodeStatus",
        nodeId: data.node_id as string,
        status: "failed",
      };
    case "run_completed":
      return {
        action: "runCompleted",
        runId: data.run_id as string,
        totalCost: data.total_cost_usd as number,
      };
    case "run_failed":
      return {
        action: "runFailed",
        runId: data.run_id as string,
        error: data.error as string,
      };
    default:
      return null;
  }
}

export function getStatusBorderColor(status: RunStatus): string {
  switch (status) {
    case "running":
      return "border-blue-500";
    case "completed":
      return "border-green-500";
    case "failed":
      return "border-red-500";
    case "paused":
      return "border-yellow-500";
    case "idle":
    case "pending":
    default:
      return "border-gray-300";
  }
}
