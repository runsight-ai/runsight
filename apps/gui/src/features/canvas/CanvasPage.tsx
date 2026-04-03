import { useLocation, useParams } from "react-router";

import { WorkflowSurfaceRoute } from "./WorkflowSurfaceRoute";
import type { WorkflowSurfaceMode } from "./workflowSurfaceContract";

interface CanvasPageLocationState {
  workflowSurfaceMode?: WorkflowSurfaceMode;
}

export function Component() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation() as { state?: CanvasPageLocationState };
  const initialMode = location.state?.workflowSurfaceMode === "fork-draft"
    ? "fork-draft"
    : "workflow";

  return (
    <WorkflowSurfaceRoute
      workflowId={id!}
      initialMode={initialMode}
    />
  );
}

export default Component;
