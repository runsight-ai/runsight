import { useState, useEffect, useRef } from "react";
import type { WorkflowSurfaceMode } from "./surfaceContract";
import type { PersistedCanvasState } from "@/store/canvas";
import type { WorkflowCanvasState } from "@runsight/shared/zod";
import { hasRenderableCanvasState, buildWorkflowLayout } from "./workflowLayout";

type CanvasHydrationParams = {
  mode: WorkflowSurfaceMode;
  resolvedWorkflowId: string;
  activeRunId: string | undefined;
  initialRunId: string | undefined;
  overlayRef: string | null;
  overlayYaml: string | null;
  readonlyYaml: string | null;
  workflow: { yaml?: string | null; canvas_state?: WorkflowCanvasState | PersistedCanvasState | Record<string, unknown> | null } | null | undefined;
  setYamlContent: (yaml: string) => void;
  hydrateFromPersisted: (state: PersistedCanvasState | null) => void;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

const DEFAULT_CANVAS_VIEWPORT = { x: 0, y: 0, zoom: 1 };

function normalizePersistedCanvasState(
  canvasState: WorkflowCanvasState | PersistedCanvasState | Record<string, unknown> | null | undefined,
): PersistedCanvasState | null {
  if (!isRecord(canvasState)) {
    return null;
  }

  const viewport =
    isRecord(canvasState.viewport)
    && typeof canvasState.viewport.x === "number"
    && typeof canvasState.viewport.y === "number"
    && typeof canvasState.viewport.zoom === "number"
      ? {
          x: canvasState.viewport.x,
          y: canvasState.viewport.y,
          zoom: canvasState.viewport.zoom,
        }
      : DEFAULT_CANVAS_VIEWPORT;

  return {
    nodes: Array.isArray(canvasState.nodes) ? canvasState.nodes.filter(isRecord) : [],
    edges: Array.isArray(canvasState.edges) ? canvasState.edges.filter(isRecord) : [],
    viewport,
    selected_node_id:
      typeof canvasState.selected_node_id === "string" ? canvasState.selected_node_id : null,
    canvas_mode: canvasState.canvas_mode === "state-machine" ? "state-machine" : "dag",
  };
}

export function useCanvasHydration(params: CanvasHydrationParams): { canvasHydrationRevision: number } {
  const {
    mode,
    resolvedWorkflowId,
    activeRunId,
    initialRunId,
    overlayRef,
    overlayYaml,
    readonlyYaml,
    workflow,
    setYamlContent,
    hydrateFromPersisted,
  } = params;

  const [canvasHydrationRevision, setCanvasHydrationRevision] = useState(0);
  const lastCanvasHydrationKeyRef = useRef<string | null>(null);

  useEffect(() => {
    if (!resolvedWorkflowId) {
      return;
    }

    const preferredYaml =
      mode === "readonly"
        ? (readonlyYaml ?? workflow?.yaml ?? null)
        : (overlayRef && overlayYaml !== null ? overlayYaml : (workflow?.yaml ?? null));

    if (!preferredYaml) {
      return;
    }

    setYamlContent(preferredYaml);

    const persistedCanvasState = normalizePersistedCanvasState(workflow?.canvas_state);
    const renderableCanvasState = hasRenderableCanvasState(persistedCanvasState);
    const hydrationKind = renderableCanvasState ? "persisted" : "computed";
    const yamlKind =
      mode === "readonly"
        ? (readonlyYaml != null ? "historical" : "live")
        : (overlayRef && overlayYaml !== null ? `overlay:${overlayRef}` : "live");
    const hydrationKey = [
      mode,
      resolvedWorkflowId,
      activeRunId ?? initialRunId ?? "",
      hydrationKind,
      yamlKind,
    ].join(":");

    if (lastCanvasHydrationKeyRef.current === hydrationKey) {
      return;
    }

    if (renderableCanvasState) {
      hydrateFromPersisted(persistedCanvasState);
    } else {
      hydrateFromPersisted(buildWorkflowLayout(preferredYaml, persistedCanvasState));
    }

    setCanvasHydrationRevision((revision) => revision + 1);
    lastCanvasHydrationKeyRef.current = hydrationKey;
  }, [
    activeRunId,
    hydrateFromPersisted,
    initialRunId,
    mode,
    overlayRef,
    overlayYaml,
    readonlyYaml,
    resolvedWorkflowId,
    setYamlContent,
    workflow?.canvas_state,
    workflow?.yaml,
  ]);

  return { canvasHydrationRevision };
}
