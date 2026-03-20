import { create } from "zustand";
import {
  applyEdgeChanges,
  applyNodeChanges,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
  type Viewport,
} from "@xyflow/react";
import type { RunStatus, StepNodeData } from "../types/schemas/canvas";

export type CanvasMode = "dag" | "state-machine";

export interface PersistedCanvasState {
  nodes: Record<string, unknown>[];
  edges: Record<string, unknown>[];
  viewport: Viewport;
  selected_node_id: string | null;
  canvas_mode: CanvasMode;
}

interface CanvasState {
  nodes: Node[];
  edges: Edge[];
  viewport: Viewport;
  isDirty: boolean;
  selectedNodeId: string | null;
  canvasMode: CanvasMode;
  validationErrors: string[];
  hasValidationErrors: boolean;
  activeRunId: string | null;
  runCost: number;
  setNodes: (nodes: Node[], markDirty?: boolean) => void;
  setEdges: (edges: Edge[], markDirty?: boolean) => void;
  onNodesChange: (changes: NodeChange[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  setViewport: (viewport: Viewport, markDirty?: boolean) => void;
  selectNode: (id: string | null) => void;
  setCanvasMode: (mode: CanvasMode) => void;
  setValidationErrors: (errors: string[]) => void;
  setActiveRunId: (runId: string | null) => void;
  setRunCost: (cost: number) => void;
  setNodeStatus: (nodeId: string, status: RunStatus) => void;
  resetNodeStatuses: () => void;
  hydrateFromPersisted: (state: PersistedCanvasState | null | undefined) => void;
  toPersistedState: () => PersistedCanvasState;
  markSaved: () => void;
  reset: () => void;
}

const DEFAULT_VIEWPORT: Viewport = { x: 0, y: 0, zoom: 1 };

const initialState = {
  nodes: [] as Node[],
  edges: [] as Edge[],
  viewport: DEFAULT_VIEWPORT,
  isDirty: false,
  selectedNodeId: null as string | null,
  canvasMode: "dag" as CanvasMode,
  validationErrors: [] as string[],
  hasValidationErrors: false,
  activeRunId: null as string | null,
  runCost: 0,
};

export const useCanvasStore = create<CanvasState>((set, get) => ({
  ...initialState,
  setNodes: (nodes, markDirty = true) => set({ nodes, isDirty: markDirty || get().isDirty }),
  setEdges: (edges, markDirty = true) => set({ edges, isDirty: markDirty || get().isDirty }),
  onNodesChange: (changes) =>
    set((state) => ({
      nodes: applyNodeChanges(changes, state.nodes),
      isDirty: true,
    })),
  onEdgesChange: (changes) =>
    set((state) => ({
      edges: applyEdgeChanges(changes, state.edges),
      isDirty: true,
    })),
  setViewport: (viewport, markDirty = true) =>
    set({ viewport, isDirty: markDirty || get().isDirty }),
  selectNode: (id) => set({ selectedNodeId: id }),
  setCanvasMode: (mode) => set({ canvasMode: mode, isDirty: true }),
  setValidationErrors: (errors) =>
    set({ validationErrors: errors, hasValidationErrors: errors.length > 0 }),
  setActiveRunId: (runId) => set({ activeRunId: runId }),
  setRunCost: (cost) => set({ runCost: cost }),
  setNodeStatus: (nodeId, status) =>
    set((state) => ({
      nodes: state.nodes.map((node) =>
        node.id === nodeId
          ? { ...node, data: { ...node.data, status } as StepNodeData }
          : node,
      ),
    })),
  resetNodeStatuses: () =>
    set((state) => ({
      nodes: state.nodes.map((node) => ({
        ...node,
        data: { ...node.data, status: "idle" } as StepNodeData,
      })),
    })),
  hydrateFromPersisted: (state) => {
    if (!state) {
      set({ ...initialState });
      return;
    }

    set({
      nodes: (state.nodes as Node[]) ?? [],
      edges: (state.edges as Edge[]) ?? [],
      viewport: state.viewport ?? DEFAULT_VIEWPORT,
      selectedNodeId: state.selected_node_id ?? null,
      canvasMode: state.canvas_mode ?? "dag",
      isDirty: false,
    });
  },
  toPersistedState: () => {
    const state = get();
    return {
      nodes: state.nodes as unknown as Record<string, unknown>[],
      edges: state.edges as unknown as Record<string, unknown>[],
      viewport: state.viewport,
      selected_node_id: state.selectedNodeId,
      canvas_mode: state.canvasMode,
    };
  },
  markSaved: () => set({ isDirty: false }),
  reset: () => set({ ...initialState }),
}));
