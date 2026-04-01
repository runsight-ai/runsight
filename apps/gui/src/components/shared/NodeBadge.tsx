import { cva } from "class-variance-authority";
import { cn } from "@runsight/ui/utils";

// ---------------------------------------------------------------------------
// CVA base — outline badge variant (badge--outline spec)
// transparent bg, border-default, text-secondary
// ---------------------------------------------------------------------------

const nodeBadgeVariants = cva(
  [
    "inline-flex items-center gap-1",
    "px-2 py-0.5",
    "font-mono text-[length:var(--font-size-2xs)] font-medium",
    "tracking-[var(--tracking-wide)] uppercase",
    "leading-[var(--line-height-tight)]",
    "rounded-full",
    "border border-(--border-default)",
    "bg-transparent text-(--text-secondary)",
    "whitespace-nowrap",
  ].join(" ")
);

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type NodeType = "soul" | "task" | "team" | "branch";

interface NodeBadgeProps {
  type: NodeType;
  label?: string;
  className?: string;
}

// Maps NodeType → Tailwind dot colour + default label
const nodeConfig: Record<NodeType, { dotClass: string; defaultLabel: string }> = {
  soul:   { dotClass: "bg-(--block-agent)",   defaultLabel: "Soul"   },
  task:   { dotClass: "bg-(--block-logic)",   defaultLabel: "Task"   },
  team:   { dotClass: "bg-(--block-control)", defaultLabel: "Team"   },
  branch: { dotClass: "bg-(--block-utility)", defaultLabel: "Branch" },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function NodeBadge({ type, label, className }: NodeBadgeProps) {
  const config = nodeConfig[type];
  const displayLabel = label ?? config.defaultLabel;

  return (
    <div className={cn(nodeBadgeVariants(), className)}>
      {/* Coloured dot indicator */}
      <span
        className={cn("w-1.5 h-1.5 rounded-full flex-shrink-0", config.dotClass)}
        aria-hidden="true"
      />
      <span>{displayLabel}</span>
    </div>
  );
}
