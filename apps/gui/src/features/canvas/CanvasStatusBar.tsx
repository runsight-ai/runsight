import { StatusDot } from "@runsight/ui/status-dot";
import { useProviders } from "@/queries/settings";

interface CanvasStatusBarProps {
  activeTab: string;
  blockCount?: number;
  edgeCount?: number;
}

export function CanvasStatusBar({
  activeTab,
  blockCount = 0,
  edgeCount = 0,
}: CanvasStatusBarProps) {
  const { data: providers } = useProviders();
  const items = providers?.items ?? [];
  const connected = items.length > 0;
  const providerName = connected ? items[0]?.name ?? "No provider" : "No provider";

  return (
    <footer
      className="flex items-center gap-3 px-3 h-[var(--status-bar-height)] border-t border-[var(--border-subtle)] bg-[var(--surface-secondary)] text-xs text-[var(--text-muted)]"
      style={{ gridColumn: "1 / -1", gridRow: "4" }}
    >
      <span className="flex items-center gap-1.5">
        <StatusDot variant={connected ? "success" : "danger"} />
        <span>{providerName}</span>
      </span>
      <span>{blockCount} {blockCount === 1 ? "block" : "blocks"}</span>
      <span>{edgeCount} {edgeCount === 1 ? "edge" : "edges"}</span>
      <span className="ml-auto">{activeTab === "yaml" ? "YAML" : "Canvas"}</span>
    </footer>
  );
}
