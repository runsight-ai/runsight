import { useParams } from "react-router";

import { WorkflowSurfaceRoute } from "../canvas/WorkflowSurfaceRoute";

export { RunCanvasNode, CanvasNode } from "./HistoricalRunSurfaceRoute";

export function Component() {
  const { id } = useParams<{ id: string }>();

  return (
    <WorkflowSurfaceRoute
      runId={id!}
      initialMode="historical"
    />
  );
}

export default Component;
