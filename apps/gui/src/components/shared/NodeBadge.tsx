import { cn } from "@/utils/helpers";

export type NodeType = "soul" | "task" | "team" | "branch";

interface NodeBadgeProps {
  type: NodeType;
  label?: string;
  className?: string;
}

const nodeConfig: Record<NodeType, { dotColor: string; defaultLabel: string }> = {
  soul: {
    dotColor: "bg-block-agent",
    defaultLabel: "Soul",
  },
  task: {
    dotColor: "bg-block-logic",
    defaultLabel: "Task",
  },
  team: {
    dotColor: "bg-block-control",
    defaultLabel: "Team",
  },
  branch: {
    dotColor: "bg-block-utility",
    defaultLabel: "Branch",
  },
};

export function NodeBadge({ type, label, className }: NodeBadgeProps) {
  const config = nodeConfig[type];
  const displayLabel = label ?? config.defaultLabel;

  return (
    <div className={cn("badge badge--outline", className)}>
      <span className={cn("badge__dot", config.dotColor)} />
      <span>{displayLabel}</span>
    </div>
  );
}
