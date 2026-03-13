import { cn } from "@/utils/helpers";

export type NodeType = "soul" | "task" | "team" | "branch";

interface NodeBadgeProps {
  type: NodeType;
  label?: string;
  className?: string;
}

const nodeConfig: Record<NodeType, { color: string; defaultLabel: string }> = {
  soul: {
    color: "bg-[var(--node-soul)]",
    defaultLabel: "Soul",
  },
  task: {
    color: "bg-[var(--node-task)]",
    defaultLabel: "Task",
  },
  team: {
    color: "bg-[var(--node-team)]",
    defaultLabel: "Team",
  },
  branch: {
    color: "bg-[var(--node-branch)]",
    defaultLabel: "Branch",
  },
};

export function NodeBadge({ type, label, className }: NodeBadgeProps) {
  const config = nodeConfig[type];
  const displayLabel = label ?? config.defaultLabel;

  return (
    <div
      className={cn(
        "inline-flex h-6 items-center gap-1.5 rounded-full border border-border bg-muted px-2 text-xs font-medium text-secondary-foreground",
        className
      )}
    >
      <span className={cn("h-2 w-2 rounded-full", config.color)} />
      <span>{displayLabel}</span>
    </div>
  );
}
