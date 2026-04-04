import { StatusDot } from "@runsight/ui/status-dot";
import { useProviders } from "@/queries/settings";

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
  const { data: providers } = useProviders();
  const activeProviders = (providers?.items ?? []).filter((provider) => provider.is_active ?? true);
  const connected = activeProviders.length > 0;
  const providerName = connected ? activeProviders[0]?.name ?? "No provider" : "No provider";

  const stepCountDisplay =
    stepCountFormat === "progress"
      ? `${blockCount}/${blockCount} steps`
      : `${blockCount} ${blockCount === 1 ? "block" : "blocks"} \u00b7 ${edgeCount} ${edgeCount === 1 ? "edge" : "edges"}`;

  return (
    <footer
      className="flex items-center gap-3 px-3 h-[var(--status-bar-height)] border-t border-border-subtle bg-surface-secondary text-xs text-muted"
      style={{ gridColumn: "1 / -1", gridRow: "4" }}
    >
      <span className="flex items-center gap-1.5">
        <StatusDot variant={connected ? "success" : "danger"} />
        <span>{providerName}</span>
      </span>
      <span>{stepCountDisplay}</span>
      {metricsVisibility !== "hidden" && (
        <span>
          {metricsVisibility === "elapsed-and-cost" ? "elapsed: -- | cost: --" : "duration: -- | cost: --"}
        </span>
      )}
      <span className="ml-auto">{activeTab === "yaml" ? "YAML" : "Canvas"}</span>
    </footer>
  );
}
