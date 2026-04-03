import type { ReactNode } from "react";

import {
  getWorkflowSurfaceModeConfig,
  type WorkflowSurfaceProps,
} from "./workflowSurfaceContract";

interface WorkflowSurfaceLayoutProps extends WorkflowSurfaceProps {
  topbar?: ReactNode;
  palette?: ReactNode;
  mainContent: ReactNode;
  inspector?: ReactNode;
  footer?: ReactNode;
  statusBar?: ReactNode;
}

export function WorkflowSurface({
  workflowId,
  runId,
  initialMode,
  hasRunOverlay,
  isEditable,
  topbar,
  palette,
  mainContent,
  inspector,
  footer,
  statusBar,
}: WorkflowSurfaceLayoutProps) {
  const modeConfig = getWorkflowSurfaceModeConfig(initialMode);
  const surfaceUsesRunOverlay = hasRunOverlay ?? modeConfig.capabilities.usesRunOverlay;
  const surfaceIsEditable = isEditable ?? !modeConfig.capabilities.readOnly;
  const surfaceColumns =
    modeConfig.regions.palette.visible && palette ? "240px 1fr" : "1fr";
  const centerSpan =
    modeConfig.regions.palette.visible && palette ? "2 / 3" : "1 / -1";
  const inspectorContent =
    modeConfig.regions.inspector.visible && inspector ? inspector : null;
  const mainContentLabel =
    initialMode === "historical" ? "historical workflow surface" : "workflow surface";

  return (
    <div
      data-layout="workflow-surface"
      data-mode={initialMode}
      data-workflow-id={workflowId}
      data-run-id={runId}
      data-has-run-overlay={surfaceUsesRunOverlay}
      data-editable={surfaceIsEditable}
      className="grid h-full"
      style={{
        gridTemplateRows: "var(--header-height) 1fr 37px var(--status-bar-height)",
        gridTemplateColumns: surfaceColumns,
      }}
    >
      {modeConfig.regions.topbar.visible ? topbar : null}
      {modeConfig.regions.palette.visible ? palette ?? null : null}
      {modeConfig.regions.center.visible ? (
        <div
          aria-label={mainContentLabel}
          className="relative flex flex-col overflow-hidden"
          style={{ gridColumn: centerSpan, gridRow: "2" }}
        >
          <div className="flex flex-1 overflow-hidden">
            <div className="flex-1 min-w-0">{mainContent}</div>
            {inspectorContent}
          </div>
        </div>
      ) : null}
      {modeConfig.regions.footer.visible ? footer : null}
      {modeConfig.regions.statusBar.visible ? statusBar : null}
    </div>
  );
}

export const Component = WorkflowSurface;

export default WorkflowSurface;
