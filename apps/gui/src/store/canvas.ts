import { create } from "zustand";

interface CanvasState {
  selectedNodeId: string | null;
  canvasMode: "dag" | "hsm";
  selectNode: (id: string | null) => void;
  setCanvasMode: (mode: CanvasState["canvasMode"]) => void;
}

export const useCanvasStore = create<CanvasState>((set) => ({
  selectedNodeId: null,
  canvasMode: "dag",
  selectNode: (id) => set({ selectedNodeId: id }),
  setCanvasMode: (mode) => set({ canvasMode: mode }),
}));
