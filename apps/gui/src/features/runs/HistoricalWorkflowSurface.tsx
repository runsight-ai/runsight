import type { ReactNode } from "react";

import { WorkflowSurface } from "../canvas/WorkflowSurface";
import { getWorkflowSurfaceModeConfig } from "../canvas/workflowSurfaceContract";

interface HistoricalWorkflowSurfaceProps {
  runId: string;
  topbar: ReactNode;
  mainContent: ReactNode;
  inspector?: ReactNode;
  footer?: ReactNode;
}

export function HistoricalWorkflowSurface({
  runId,
  topbar,
  mainContent,
  inspector,
  footer,
}: HistoricalWorkflowSurfaceProps) {
  const historicalSurface = getWorkflowSurfaceModeConfig("historical");

  return (
    <WorkflowSurface
      initialMode="historical"
      runId={runId}
      hasRunOverlay={historicalSurface.capabilities.usesRunOverlay}
      isEditable={historicalSurface.regions.center.editable}
      topbar={topbar}
      mainContent={mainContent}
      inspector={inspector}
      footer={footer}
    />
  );
}

export const Component = HistoricalWorkflowSurface;

export default HistoricalWorkflowSurface;
