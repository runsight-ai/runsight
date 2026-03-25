// Design system tokens: surface-secondary, border-subtle, radius-md,
// font-mono, font-size-xs, font-size-2xl, text-secondary, text-heading,
// space-4, uppercase, border-t (top stripe)

import * as React from "react"

import { cn } from "@/utils/helpers"

type StatCardVariant = "default" | "accent" | "success" | "danger"

const stripeColorMap: Record<StatCardVariant, string> = {
  default: "bg-border-default",
  accent:  "bg-interactive-default",
  success: "bg-success-9",
  danger:  "bg-danger-9",
}

export interface StatCardProps extends React.ComponentProps<"div"> {
  /** Metric label — displayed uppercase in font-size-xs */
  label: string
  /** Metric value — displayed in font-mono font-size-2xl */
  value: React.ReactNode
  /** Optional delta/change/trend indicator (positive or negative) */
  delta?: React.ReactNode
  /** Visual variant controls the top category stripe color */
  variant?: StatCardVariant
  /** Optional icon displayed alongside the value */
  icon?: React.ReactNode
}

export function StatCard({
  label,
  value,
  delta,
  variant = "default",
  icon,
  className,
  ...props
}: StatCardProps) {
  const isPositiveDelta =
    typeof delta === "string" && (delta.startsWith("+") || delta.startsWith("↑"))
  const isNegativeDelta =
    typeof delta === "string" && (delta.startsWith("-") || delta.startsWith("↓"))

  return (
    <div
      data-slot="stat-card"
      data-variant={variant}
      className={cn(
        "group/stat-card relative flex flex-col gap-2 overflow-hidden rounded-radius-md border border-border-subtle bg-surface-secondary p-space-4",
        className
      )}
      {...props}
    >
      {/* Top 3px category stripe — border-t used as decorative accent bar */}
      <span
        aria-hidden="true"
        data-slot="stat-card-stripe"
        className={cn(
          "stripe absolute inset-x-0 top-0 h-[3px] border-t-0",
          stripeColorMap[variant]
        )}
      />

      {/* Label — text-secondary, font-size-xs, uppercase */}
      <span
        data-slot="stat-card-label"
        className="text-secondary text-font-size-xs uppercase tracking-wider font-mono"
      >
        {label}
      </span>

      {/* Value row */}
      <div className="flex items-end gap-2">
        <span
          data-slot="stat-card-value"
          className="font-mono text-font-size-2xl font-bold text-heading leading-none tracking-tighter"
        >
          {value}
        </span>
        {icon && (
          <span aria-hidden="true" className="mb-0.5 text-secondary">
            {icon}
          </span>
        )}
      </div>

      {/* Delta / change / trend badge */}
      {delta !== undefined && delta !== null && (
        <span
          data-slot="stat-card-delta"
          className={cn(
            "inline-flex items-center gap-0.5 text-font-size-xs font-mono",
            isPositiveDelta && "text-success-11",
            isNegativeDelta && "text-danger-11",
            !isPositiveDelta && !isNegativeDelta && "text-secondary"
          )}
        >
          {delta}
        </span>
      )}
    </div>
  )
}
