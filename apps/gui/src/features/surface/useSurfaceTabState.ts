import { useState, useEffect } from "react";

type SurfaceTabStateResult = {
  activeTab: "canvas" | "yaml";
  setActiveTab: (tab: "canvas" | "yaml") => void;
  isDirty: boolean;
  setIsDirty: (dirty: boolean) => void;
  inspectedNodeId: string | null;
  setInspectedNodeId: (id: string | null) => void;
  inspectorTab: "execution" | "overview" | "context";
  setInspectorTab: (tab: "execution" | "overview" | "context") => void;
};

export function useSurfaceTabState(yamlTabAllowed: boolean): SurfaceTabStateResult {
  const [activeTab, setActiveTab] = useState<"canvas" | "yaml">("yaml");
  const [isDirty, setIsDirty] = useState(false);
  const [inspectedNodeId, setInspectedNodeId] = useState<string | null>(null);
  const [inspectorTab, setInspectorTab] = useState<"execution" | "overview" | "context">("execution");

  useEffect(() => {
    if (!yamlTabAllowed) {
      setActiveTab("canvas");
    }
  }, [yamlTabAllowed]);

  return { activeTab, setActiveTab, isDirty, setIsDirty, inspectedNodeId, setInspectedNodeId, inspectorTab, setInspectorTab };
}
