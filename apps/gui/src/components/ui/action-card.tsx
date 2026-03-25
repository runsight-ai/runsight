// Design system tokens: surface-secondary (background), border-subtle (border),
// text-heading (title), text-primary (body text), radius-lg (border radius),
// space-4 (padding), border-l (left stripe)

import * as React from "react"

import { cn } from "@/utils/helpers"

type ActionCardVariant = "default" | "accent" | "success" | "danger" | "warning"

const stripeColorMap: Record<ActionCardVariant, string> = {
  default: "bg-border-default",
  accent:  "bg-interactive-default",
  success: "bg-success-9",
  danger:  "bg-danger-9",
  warning: "bg-warning-9",
}

export interface ActionCardProps extends React.ComponentProps<"div"> {
  /** Card title — displayed with text-heading */
  title: React.ReactNode
  /** Card description — displayed with text-secondary */
  description?: React.ReactNode
  /** Action area — typically a Button or link */
  action?: React.ReactNode
  /** Variant controls the left 3px accent stripe color */
  variant?: ActionCardVariant
}

export function ActionCard({
  title,
  description,
  action,
  variant = "default",
  className,
  ...props
}: ActionCardProps) {
  return (
    <div
      data-slot="action-card"
      data-variant={variant}
      className={cn(
        "group/action-card relative flex gap-4 overflow-hidden rounded-radius-lg border border-border-subtle bg-surface-secondary p-space-4",
        className
      )}
      {...props}
    >
      {/* Left 3px accent stripe — border-l used as decorative left border */}
      <span
        aria-hidden="true"
        data-slot="action-card-stripe"
        className={cn(
          "stripe absolute inset-y-0 left-0 w-[3px] border-l-0",
          stripeColorMap[variant]
        )}
      />

      {/* Content area — offset to clear the stripe */}
      <div className="ml-1 flex flex-1 flex-col gap-1.5">
        {/* Title */}
        <div
          data-slot="action-card-title"
          className="text-heading font-medium leading-snug text-primary"
        >
          {title}
        </div>

        {/* Description */}
        {description !== undefined && description !== null && (
          <div
            data-slot="action-card-description"
            className="text-font-size-sm text-secondary"
          >
            {description}
          </div>
        )}
      </div>

      {/* Action area — typically a Button */}
      {action !== undefined && action !== null && (
        <div
          data-slot="action-card-action"
          className="flex shrink-0 items-start"
        >
          {action}
        </div>
      )}
    </div>
  )
}
