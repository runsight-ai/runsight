import { useState, useEffect } from "react";

type SurfaceTabStateResult = {
  activeTab: "canvas" | "yaml";
  setActiveTab: (tab: "canvas" | "yaml") => void;
  isDirty: boolean;
  setIsDirty: (dirty: boolean) => void;
  inspectedNodeId: string | null;
  setInspectedNodeId: (id: string | null) => void;
};

export function useSurfaceTabState(yamlTabAllowed: boolean): SurfaceTabStateResult {
  const [activeTab, setActiveTab] = useState<"canvas" | "yaml">("yaml");
  const [isDirty, setIsDirty] = useState(false);
  const [inspectedNodeId, setInspectedNodeId] = useState<string | null>(null);

  useEffect(() => {
    if (!yamlTabAllowed) {
      setActiveTab("canvas");
    }
  }, [yamlTabAllowed]);

  return { activeTab, setActiveTab, isDirty, setIsDirty, inspectedNodeId, setInspectedNodeId };
}
