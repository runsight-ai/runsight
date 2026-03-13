import { create } from "zustand";

interface UiState {
  sidebarOpen: boolean;
  inspectorOpen: boolean;
  activeSidebarTab: "souls" | "tasks" | "steps";
  activeInspectorTab: "properties" | "prompt" | "yaml";
  toggleSidebar: () => void;
  toggleInspector: () => void;
  setSidebarTab: (tab: UiState["activeSidebarTab"]) => void;
  setInspectorTab: (tab: UiState["activeInspectorTab"]) => void;
}

export const useUiStore = create<UiState>((set) => ({
  sidebarOpen: true,
  inspectorOpen: true,
  activeSidebarTab: "souls",
  activeInspectorTab: "properties",
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  toggleInspector: () => set((s) => ({ inspectorOpen: !s.inspectorOpen })),
  setSidebarTab: (tab) => set({ activeSidebarTab: tab }),
  setInspectorTab: (tab) => set({ activeInspectorTab: tab }),
}));
