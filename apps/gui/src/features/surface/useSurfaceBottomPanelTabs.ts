import { useState } from "react";

type BottomPanelTab = "logs" | "runs" | "regressions" | "audit";

type UseSurfaceBottomPanelTabsParams = {
  defaultState?: "collapsed" | "expanded";
  onAuditOpen?: () => void;
};

export function useSurfaceBottomPanelTabs({
  defaultState = "collapsed",
  onAuditOpen,
}: UseSurfaceBottomPanelTabsParams) {
  const [isExpanded, setIsExpanded] = useState(defaultState === "expanded");
  const [activeTab, setActiveTab] = useState<BottomPanelTab>("logs");

  const openTab = (tab: BottomPanelTab) => {
    setActiveTab(tab);
    setIsExpanded(true);
    if (tab === "audit") {
      onAuditOpen?.();
    }
  };

  const toggleExpanded = () => {
    setIsExpanded((expanded) => !expanded);
  };

  return {
    activeTab,
    isExpanded,
    openTab,
    toggleExpanded,
  };
}
