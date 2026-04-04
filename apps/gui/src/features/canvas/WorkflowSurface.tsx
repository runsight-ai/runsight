import { useState, useEffect, useCallback } from "react";
import type { Node } from "@xyflow/react";
import type { WorkflowSurfaceProps, WorkflowSurfaceMode } from "./workflowSurfaceContract";
import { getContractForMode, getCanvasYamlToggleVisibility, getSaveButtonState, getActionButton, isEditable } from "./workflowSurfaceContract";
import { CanvasTopbar } from "./CanvasTopbar";
import { PaletteSidebar } from "./PaletteSidebar";
import { WorkflowCanvas } from "./WorkflowCanvas";
import { YamlEditor } from "./YamlEditor";
import { CanvasBottomPanel } from "./CanvasBottomPanel";
import { CanvasStatusBar } from "./CanvasStatusBar";
import { RunInspectorPanel } from "../runs/RunInspectorPanel";
import type { RunNodeData } from "../runs/RunCanvasNode";
import { useCanvasStore } from "@/store/canvas";

export function WorkflowSurface({ mode: initialMode, workflowId: initialWorkflowId = "", runId: initialRunId }: WorkflowSurfaceProps) {
  const [mode, setMode] = useState<WorkflowSurfaceMode>(initialMode);
  const [workflowId, setWorkflowId] = useState(initialWorkflowId);
  const [activeRunId, setRunId] = useState(initialRunId);

  const handleForkTransition = useCallback((newWorkflowId: string) => {
    setMode("edit");
    setWorkflowId(newWorkflowId);
    setRunId(undefined);
    window.history.replaceState(null, "", `/workflows/${newWorkflowId}/edit`);
  }, []);

  const contract = getContractForMode(mode);

  const { topbar, palette, canvas, inspector, bottomPanel, statusBar } = contract;

  const nameEditable = topbar.nameEditable;
  const dimmed = palette.dimmed;
  const isDraggable = canvas.draggable;
  const connectionsAllowed = canvas.connectionsAllowed;
  const deletionAllowed = canvas.deletionAllowed;
  const defaultState = bottomPanel.defaultState;
  const trigger = inspector.trigger;
  const stepCountFormat = statusBar.stepCountFormat;
  const metricsVisibility = statusBar.metricsVisibility;
  const toggleVisibility = getCanvasYamlToggleVisibility(mode);
  const editable = isEditable(mode);

  const [activeTab, setActiveTab] = useState<"canvas" | "yaml">("canvas");
  const [isDirty, setIsDirty] = useState(false);
  const [selectedNode, setSelectedNode] = useState<Node<RunNodeData> | null>(null);

  const nodes = useCanvasStore((s) => s.nodes);

  // Inspector trigger: open on single-click or double-click depending on mode
  const handleNodeClickForInspector = useCallback(
    (nodeId: string) => {
      if (trigger !== "single-click") return;
      const node = nodes.find((n) => n.id === nodeId);
      if (node) setSelectedNode(node as Node<RunNodeData>);
    },
    [trigger, nodes],
  );

  const handleNodeDoubleClickForInspector = useCallback(
    (nodeId: string) => {
      if (trigger !== "double-click") return;
      const node = nodes.find((n) => n.id === nodeId);
      if (node) setSelectedNode(node as Node<RunNodeData>);
    },
    [trigger, nodes],
  );

  const handleCloseInspector = useCallback(() => {
    setSelectedNode(null);
  }, []);

  // Force canvas tab when yaml is unavailable (execution/historical modes)
  useEffect(() => {
    if (!toggleVisibility.yaml) {
      setActiveTab("canvas");
    }
  }, [toggleVisibility.yaml]);

  const saveButtonState = getSaveButtonState(mode, isDirty);
  const actionButton = getActionButton(mode);

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
  }

  const setNodes = useCanvasStore((s) => s.setNodes);

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    if (!editable) return;

    const blockData = e.dataTransfer.getData("application/runsight-block");
    const soulData = e.dataTransfer.getData("application/runsight-soul");

    // Calculate drop position relative to the canvas container
    const bounds = e.currentTarget.getBoundingClientRect();
    const position = {
      x: e.clientX - bounds.left,
      y: e.clientY - bounds.top,
    };

    if (blockData) {
      try {
        const parsed = JSON.parse(blockData) as { type: string; label: string };
        const id = `block_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
        const newNode: Node = {
          id,
          type: "task",
          position,
          data: { label: parsed.label, blockType: parsed.label },
        };
        const currentNodes = useCanvasStore.getState().nodes;
        setNodes([...currentNodes, newNode]);
      } catch {
        // Ignore malformed drag data
      }
    }
    if (soulData) {
      try {
        const parsed = JSON.parse(soulData) as { type: string; label: string };
        const id = `soul_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
        const newNode: Node = {
          id,
          type: "soul",
          position,
          data: { label: parsed.label, soulRef: parsed.label },
        };
        const currentNodes = useCanvasStore.getState().nodes;
        setNodes([...currentNodes, newNode]);
      } catch {
        // Ignore malformed drag data
      }
    }
  }

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
          activeTab={activeTab}
          onValueChange={(v) => setActiveTab(v as "canvas" | "yaml")}
          isDirty={isDirty}
          onSave={() => {}}
          nameEditable={nameEditable}
          toggleVisibility={toggleVisibility}
          saveButton={saveButtonState}
          metricsVisible={topbar.metricsVisible}
          metricsStyle={topbar.metricsStyle}
          actionButton={actionButton}
          onForkTransition={handleForkTransition}
        />
      </div>

      <div
        data-testid="surface-palette"
        className="flex flex-col overflow-hidden"
        style={{ gridColumn: "1", gridRow: "2" }}
      >
        <PaletteSidebar interactive={!dimmed} dimmed={dimmed} />
      </div>

      <div
        data-testid="surface-center"
        className="relative flex flex-col overflow-hidden"
        style={{ gridColumn: "2", gridRow: "2" }}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
      >
        {activeTab === "canvas" ? (
          <WorkflowCanvas
            isDraggable={isDraggable}
            connectionsAllowed={connectionsAllowed}
            deletionAllowed={deletionAllowed}
            runId={activeRunId}
            onNodeClick={handleNodeClickForInspector}
            onNodeDoubleClick={handleNodeDoubleClickForInspector}
          />
        ) : activeTab === "yaml" ? (
          <YamlEditor
            workflowId={workflowId}
            readOnly={!editable}
            onDirtyChange={(dirty: boolean) => setIsDirty(dirty)}
          />
        ) : null}
      </div>

      <div
        data-testid="surface-inspector"
        style={{ gridColumn: "3", gridRow: "2" }}
      >
        <RunInspectorPanel
          selectedNode={selectedNode}
          onClose={handleCloseInspector}
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
          activeTab={activeTab}
          blockCount={0}
          edgeCount={0}
          stepCountFormat={stepCountFormat}
          metricsVisibility={metricsVisibility}
        />
      </div>
    </div>
  );
}
