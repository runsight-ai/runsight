import type { WorkflowSurfaceMode } from "./workflowSurfaceContract";
import { EditableWorkflowSurfaceRoute } from "./EditableWorkflowSurfaceRoute";
import { HistoricalRunSurfaceRoute } from "../runs/HistoricalRunSurfaceRoute";

interface WorkflowSurfaceRouteProps {
  initialMode: WorkflowSurfaceMode;
  workflowId?: string;
  runId?: string;
}

export function WorkflowSurfaceRoute({
  initialMode,
  workflowId,
  runId,
}: WorkflowSurfaceRouteProps) {
  if (initialMode === "historical") {
    if (!runId) {
      throw new Error("Historical WorkflowSurfaceRoute requires runId");
    }

    return <HistoricalRunSurfaceRoute runId={runId} />;
  }

  if (!workflowId) {
    throw new Error("Editable WorkflowSurfaceRoute requires workflowId");
  }

  return (
    <EditableWorkflowSurfaceRoute
      workflowId={workflowId}
      initialMode={initialMode}
    />
  );
}

export const Component = WorkflowSurfaceRoute;

export default WorkflowSurfaceRoute;
