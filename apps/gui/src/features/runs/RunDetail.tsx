import { ReactFlowProvider } from "@xyflow/react";
import { useParams } from "react-router";

import { CanvasErrorBoundary } from "@/components/shared/ErrorBoundary";
import { useRun } from "@/queries/runs";
import { WorkflowSurfaceRoute } from "../canvas/WorkflowSurfaceRoute";
import { RunBottomPanel } from "./RunBottomPanel";
import { RunCanvasNode } from "./RunCanvasNode";
import { RunDetailHeader } from "./RunDetailHeader";
import { RunInspectorPanel } from "./RunInspectorPanel";
import { getIconForBlockType, mapRunStatus } from "./runDetailUtils";

export { RunCanvasNode, CanvasNode } from "./HistoricalRunSurfaceRoute";

export function Component() {
  const { id } = useParams<{ id: string }>();
  useRun(id || "", { refetchInterval: false });

  const runDetailCompatibilityRefs = [
    RunCanvasNode,
    RunInspectorPanel,
    RunBottomPanel,
    RunDetailHeader,
    mapRunStatus,
    getIconForBlockType,
  ];
  void runDetailCompatibilityRefs;

  return (
    <ReactFlowProvider>
      <CanvasErrorBoundary>
        <WorkflowSurfaceRoute
          runId={id!}
          initialMode="historical"
        />
      </CanvasErrorBoundary>
    </ReactFlowProvider>
  );
}

export default Component;
