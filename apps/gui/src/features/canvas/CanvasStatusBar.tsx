interface CanvasStatusBarProps {
  activeTab: string;
  blockCount?: number;
  edgeCount?: number;
  stepCountFormat?: "steps-and-edges" | "progress";
  metricsVisibility?: "hidden" | "elapsed-and-cost" | "duration-and-cost";
}

export function CanvasStatusBar({
  activeTab,
  blockCount = 0,
  edgeCount = 0,
  stepCountFormat = "steps-and-edges",
  metricsVisibility = "hidden",
}: CanvasStatusBarProps) {
  const hasCounts = blockCount > 0 || edgeCount > 0;
  const stepCountDisplay = !hasCounts
    ? null
    : stepCountFormat === "progress"
      ? `${blockCount}/${blockCount} steps`
      : `${blockCount} ${blockCount === 1 ? "block" : "blocks"} \u00b7 ${edgeCount} ${edgeCount === 1 ? "edge" : "edges"}`;

  return (
    <footer
      className="flex items-center gap-3 px-3 h-[var(--status-bar-height)] border-t border-border-subtle bg-surface-secondary text-xs text-muted"
      style={{ gridColumn: "1 / -1", gridRow: "4" }}
    >
      {stepCountDisplay ? <span>{stepCountDisplay}</span> : <span className="opacity-0">status</span>}
      {metricsVisibility !== "hidden" ? null : null}
      <span className="ml-auto">{activeTab === "yaml" ? "YAML" : "Canvas"}</span>
    </footer>
  );
}
