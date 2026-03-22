import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router";
import Editor from "@monaco-editor/react";
import {
  addEdge,
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  type Connection,
  type Edge,
  type Node,
  type NodeProps,
  type NodeTypes,
  type Viewport,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Save, RefreshCcw, AlertTriangle, Play } from "lucide-react";
import { useWorkflow, useUpdateWorkflow } from "../../queries/workflows";
import { useCreateRun } from "../../queries/runs";
import { Button } from "../../components/ui/button";
import { useCanvasStore } from "../../store/canvas";
import type { StepNodeData } from "../../types/schemas/canvas";
import { compileGraphToWorkflowYaml } from "./yamlCompiler";
import { parseWorkflowYamlToGraph } from "./yamlParser";
import { runWorkflow } from "./runWorkflow";
import { CanvasErrorBoundary } from "../../components/shared/ErrorBoundary";

function CanvasNode({ data }: NodeProps) {
  const typedData = (data ?? {}) as Partial<StepNodeData>;
  return (
    <div className="min-w-[180px] rounded-md border border-[var(--border)] bg-[var(--card)] px-3 py-2 shadow-sm">
      <div className="text-sm font-medium text-[var(--foreground)]">
        {typedData.name ?? typedData.stepId ?? "Node"}
      </div>
      <div className="text-xs text-[var(--muted-foreground)]">{typedData.stepType ?? "unknown"}</div>
    </div>
  );
}

const nodeTypes: NodeTypes = { canvasNode: CanvasNode };

type ViewMode = "visual" | "code";
type E2eEditorHost = HTMLDivElement & { __e2eSetValue?: (text: string) => void };

function CanvasInner() {
  const { id = "" } = useParams();
  const [mode, setMode] = useState<ViewMode>("visual");
  const [yamlText, setYamlText] = useState("");
  const [parseError, setParseError] = useState<string | null>(null);
  const [hasHydrated, setHasHydrated] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const yamlTextRef = useRef("");

  const workflowQuery = useWorkflow(id);
  const updateWorkflow = useUpdateWorkflow();
  const createRunMutation = useCreateRun();
  const navigate = useNavigate();

  const nodes = useCanvasStore((s) => s.nodes) as Node<StepNodeData>[];
  const edges = useCanvasStore((s) => s.edges) as Edge[];
  const viewport = useCanvasStore((s) => s.viewport);
  const isDirty = useCanvasStore((s) => s.isDirty);
  const hasValidationErrors = useCanvasStore((s) => s.hasValidationErrors);
  const selectedNodeId = useCanvasStore((s) => s.selectedNodeId);
  const canvasMode = useCanvasStore((s) => s.canvasMode);
  const onNodesChange = useCanvasStore((s) => s.onNodesChange);
  const onEdgesChange = useCanvasStore((s) => s.onEdgesChange);
  const setEdges = useCanvasStore((s) => s.setEdges);
  const setViewport = useCanvasStore((s) => s.setViewport);
  const selectNode = useCanvasStore((s) => s.selectNode);
  const hydrateFromPersisted = useCanvasStore((s) => s.hydrateFromPersisted);
  const markSaved = useCanvasStore((s) => s.markSaved);

  const title = useMemo(() => workflowQuery.data?.name || `Workflow ${id}`, [workflowQuery.data?.name, id]);

  const setYamlTextSafely = useCallback((next: string) => {
    yamlTextRef.current = next;
    setYamlText(next);
  }, []);

  const setYamlEditorHostRef = useCallback(
    (el: HTMLDivElement | null) => {
      const host = el as E2eEditorHost | null;
      if (host) {
        host.__e2eSetValue = (text: string) => {
          setYamlTextSafely(text);
        };
      }
    },
    [setYamlTextSafely],
  );

  useEffect(() => {
    const workflow = workflowQuery.data;
    if (!workflow || hasHydrated) return;

    const sourceYaml = (workflow.yaml && workflow.yaml.trim()) || "";
    setYamlTextSafely(sourceYaml);

    const parsed = parseWorkflowYamlToGraph(sourceYaml, workflow.canvas_state ?? null);
    if (parsed.error) {
      setParseError(parsed.error.message);
      hydrateFromPersisted(workflow.canvas_state ?? null);
    } else {
      setParseError(null);
      hydrateFromPersisted({
        nodes: parsed.nodes as unknown as Record<string, unknown>[],
        edges: parsed.edges as unknown as Record<string, unknown>[],
        viewport: parsed.viewport ?? workflow.canvas_state?.viewport ?? { x: 0, y: 0, zoom: 1 },
        selected_node_id: workflow.canvas_state?.selected_node_id ?? null,
        canvas_mode: workflow.canvas_state?.canvas_mode ?? "dag",
      });
    }

    setHasHydrated(true);
  }, [workflowQuery.data, hasHydrated, hydrateFromPersisted, setYamlTextSafely]);

  const applyYamlToCanvas = () => {
    const parsed = parseWorkflowYamlToGraph(yamlTextRef.current, {
      nodes: nodes as unknown as Record<string, unknown>[],
      edges: edges as unknown as Record<string, unknown>[],
      viewport,
      selected_node_id: selectedNodeId,
      canvas_mode: canvasMode,
    });
    if (parsed.error) {
      setParseError(parsed.error.message);
      return;
    }
    setParseError(null);
    hydrateFromPersisted({
      nodes: parsed.nodes as unknown as Record<string, unknown>[],
      edges: parsed.edges as unknown as Record<string, unknown>[],
      viewport: parsed.viewport ?? viewport,
      selected_node_id: selectedNodeId,
      canvas_mode: canvasMode,
    });
  };

  const onConnect = (connection: Connection) => {
    setEdges(addEdge(connection, edges), true);
  };

  const onMoveEnd = (_event: MouseEvent | TouchEvent | null, nextViewport: Viewport) => {
    setViewport(nextViewport, true);
  };

  const onSave = async () => {
    if (!id) return;
    setIsSaving(true);
    try {
      const compiled = compileGraphToWorkflowYaml({
        nodes,
        edges,
        viewport,
        selectedNodeId,
        canvasMode,
        workflowName: title,
      });
      setYamlTextSafely(compiled.yaml);
      setParseError(null);

      await updateWorkflow.mutateAsync({
        id,
        data: {
          yaml: compiled.yaml,
          canvas_state: compiled.canvasState,
        },
      });
      markSaved();
    } finally {
      setIsSaving(false);
    }
  };

  const handleRun = async () => {
    setIsRunning(true);
    try {
      await runWorkflow({
        workflowId: id,
        save: onSave,
        createRun: createRunMutation.mutateAsync,
        navigate,
        isRunning,
        onError: (e) => console.error(e),
      });
    } finally {
      setIsRunning(false);
    }
  };

  if (workflowQuery.isLoading) {
    return (
      <div className="p-6 text-sm text-[var(--muted-foreground)]">Loading workflow...</div>
    );
  }

  return (
    <div className="h-full w-full min-h-0 flex flex-col bg-[var(--background)]">
      <div className="h-14 shrink-0 border-b border-[var(--border)] px-4 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-base font-semibold text-[var(--foreground)] truncate">{title}</h1>
          <p className="text-xs text-[var(--muted-foreground)]">Bi-directional YAML ↔ Canvas sync</p>
        </div>

        <div className="flex items-center gap-2">
          <div className="rounded-md border border-[var(--border)] bg-[var(--card)] p-1 flex items-center gap-1">
            <Button
              data-testid="canvas-mode-visual"
              variant="ghost"
              className={`h-8 px-3 ${mode === "visual" ? "bg-[var(--surface-elevated)]" : ""}`}
              onClick={() => setMode("visual")}
            >
              Visual
            </Button>
            <Button
              data-testid="canvas-mode-code"
              variant="ghost"
              className={`h-8 px-3 ${mode === "code" ? "bg-[var(--surface-elevated)]" : ""}`}
              onClick={() => setMode("code")}
            >
              Code
            </Button>
          </div>
          <Button data-testid="canvas-apply-yaml" variant="outline" className="h-8 px-3" onClick={applyYamlToCanvas}>
            <RefreshCcw className="size-3.5 mr-1.5" />
            Apply YAML
          </Button>
          <Button data-testid="canvas-save" className="h-8 px-3" onClick={onSave} disabled={isSaving}>
            <Save className="size-3.5 mr-1.5" />
            {isSaving ? "Saving..." : isDirty ? "Save*" : "Save"}
          </Button>
          <Button
            data-testid="canvas-run"
            className="h-8 px-3"
            onClick={handleRun}
            disabled={isRunning || hasValidationErrors || isSaving}
          >
            <Play className="size-3.5 mr-1.5" />
            {isRunning ? "Running..." : "Run"}
          </Button>
        </div>
      </div>

      {parseError && (
        <div data-testid="canvas-parse-error" className="shrink-0 mx-4 mt-3 rounded-md border border-[var(--error-20)] bg-[var(--error-08)] px-3 py-2 flex items-start gap-2">
          <AlertTriangle className="size-4 text-[var(--error)] mt-0.5" />
          <div className="text-xs text-[var(--error)] whitespace-pre-wrap">{parseError}</div>
        </div>
      )}

      <div className="min-h-0 flex-1 p-4 pt-3">
        {mode === "visual" ? (
          <div className="h-full w-full rounded-lg border border-[var(--border)] overflow-hidden">
            <CanvasErrorBoundary>
              <ReactFlow
                data-testid="canvas-reactflow"
                nodes={nodes}
                edges={edges}
                nodeTypes={nodeTypes}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                onSelectionChange={(sel) => selectNode(sel.nodes[0]?.id ?? null)}
                onMoveEnd={onMoveEnd}
                fitView
              >
                <MiniMap />
                <Controls />
                <Background />
              </ReactFlow>
            </CanvasErrorBoundary>
          </div>
        ) : (
          <div className="h-full w-full rounded-lg border border-[var(--border)] overflow-hidden">
            <div ref={setYamlEditorHostRef} data-testid="canvas-yaml-editor" className="h-full w-full">
              <Editor
                language="yaml"
                value={yamlText}
                onChange={(next) => setYamlTextSafely(next ?? "")}
                theme="vs-dark"
                options={{
                  minimap: { enabled: false },
                  fontSize: 13,
                  wordWrap: "on",
                  scrollBeyondLastLine: false,
                }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function Component() {
  return (
    <ReactFlowProvider>
      <CanvasInner />
    </ReactFlowProvider>
  );
}
