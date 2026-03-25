// Design system tokens: surface-secondary (background), border-subtle (border),
// text-heading (title), text-primary (body text), radius-lg (border radius),
// space-4 (padding), border-l (left stripe)

import * as React from "react"

import { cn } from "@/utils/helpers"

type ActionCardVariant = "default" | "accent" | "success" | "danger" | "warning"

/** Maps variant to CSS custom property value for the left stripe colour */
const stripeVarMap: Record<ActionCardVariant, string> = {
  default: "var(--border-default)",
  accent:  "var(--interactive-default)",
  success: "var(--success-9)",
  danger:  "var(--danger-9)",
  warning: "var(--warning-9)",
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
    // .card base provides: surface-secondary bg, border-subtle border, radius-lg, overflow:hidden
    <div
      data-slot="action-card"
      data-variant={variant}
      className={cn("bg-(--surface-secondary) border border-(--border-subtle) rounded-[var(--radius-lg)] overflow-hidden relative flex gap-4 p-4", className)}
      {...props}
    >
      {/* Left 3px accent stripe — inline var(--token) for variant colour */}
      <span
        aria-hidden="true"
        data-slot="action-card-stripe"
        className="absolute inset-y-0 left-0 w-[3px]"
        style={{ background: stripeVarMap[variant] }}
      />

      {/* Content area — offset to clear the stripe */}
      <div className="ml-1 flex flex-1 flex-col gap-1.5">
        {/* Title — text-heading */}
        <div
          data-slot="action-card-title"
          className="text-heading font-medium leading-snug text-primary"
        >
          {title}
        </div>

        {/* Description — text-secondary + font-size-sm */}
        {description !== undefined && description !== null && (
          <div
            data-slot="action-card-description"
            className="text-sm text-secondary"
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
