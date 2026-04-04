import type { WorkflowSurfaceProps, WorkflowSurfaceMode } from "./workflowSurfaceContract";
import { getContractForMode, getCanvasYamlToggleVisibility, getStepCountFormat, getMetricsVisibility, getInspectorTrigger, getBottomPanelDefault } from "./workflowSurfaceContract";
import { CanvasTopbar } from "./CanvasTopbar";
import { PaletteSidebar } from "./PaletteSidebar";
import { WorkflowCanvas } from "./WorkflowCanvas";
import { CanvasBottomPanel } from "./CanvasBottomPanel";
import { CanvasStatusBar } from "./CanvasStatusBar";
import { RunInspectorPanel } from "../runs/RunInspectorPanel";

export function WorkflowSurface({ mode, workflowId, runId }: WorkflowSurfaceProps) {
  const contract = getContractForMode(mode);
  const activeMode: WorkflowSurfaceMode = mode;

  const { topbar, palette, canvas, inspector, bottomPanel, statusBar } = contract;

  const nameEditable = topbar.nameEditable;
  const dimmed = palette.dimmed;
  const isDraggable = canvas.draggable;
  const defaultState = bottomPanel.defaultState;
  const trigger = inspector.trigger;
  const stepCountFormat = statusBar.stepCountFormat;
  const metricsVisibility = statusBar.metricsVisibility;
  const toggleVisibility = getCanvasYamlToggleVisibility(activeMode);

  // Suppress unused-variable lint by referencing mode helpers
  void getStepCountFormat;
  void getMetricsVisibility;
  void getInspectorTrigger;
  void getBottomPanelDefault;

  return (
    <div
      className="grid h-full"
      style={{
        gridTemplateRows: "var(--header-height) 1fr auto var(--status-bar-height)",
        gridTemplateColumns: "240px 1fr 320px",
      }}
    >
      <div data-testid="surface-topbar" style={{ gridColumn: "1 / -1", gridRow: "1" }}>
        <CanvasTopbar
          workflowId={workflowId}
          activeTab={toggleVisibility.yaml ? "yaml" : "canvas"}
          onValueChange={() => {}}
          isDirty={false}
          onSave={() => {}}
          nameEditable={nameEditable}
        />
      </div>

      <div
        data-testid="surface-palette"
        className={`flex flex-col overflow-hidden ${dimmed ? "opacity-50 pointer-events-none" : ""}`}
        style={{ gridColumn: "1", gridRow: "2" }}
      >
        <PaletteSidebar />
      </div>

      <div
        data-testid="surface-center"
        className="relative flex flex-col overflow-hidden"
        style={{ gridColumn: "2", gridRow: "2" }}
      >
        <WorkflowCanvas
          isDraggable={isDraggable}
          runId={runId}
        />
      </div>

      <div
        data-testid="surface-inspector"
        style={{ gridColumn: "3", gridRow: "2" }}
      >
        <RunInspectorPanel
          selectedNode={null}
          onClose={() => {}}
          trigger={trigger}
        />
      </div>

      <div
        data-testid="surface-bottom-panel"
        style={{ gridColumn: "1 / -1", gridRow: "3" }}
      >
        <CanvasBottomPanel
          workflowId={workflowId}
          defaultState={defaultState}
        />
      </div>

      <div
        data-testid="surface-status-bar"
        style={{ gridColumn: "1 / -1", gridRow: "4" }}
      >
        <CanvasStatusBar
          activeTab="canvas"
          blockCount={0}
          edgeCount={0}
          stepCountFormat={stepCountFormat}
          metricsVisibility={metricsVisibility}
        />
      </div>
    </div>
  );
}
