// BEM classes: .stat-card, .stat-card--accent, .stat-card--success, .stat-card--danger
// .stat-card__label, .stat-card__value, .stat-card__trend, .stat-card__trend--up, .stat-card__trend--down
// Tokens: surface-tertiary, border-subtle, border-top (3px stripe), radius-md, space-4
// text-secondary, font-size-xs, font-mono, font-size-2xl (font-size-3xl in CSS), text-heading
// success-11, danger-11

import * as React from "react"

import { cn } from "@/utils/helpers"

type StatCardVariant = "default" | "accent" | "success" | "danger"

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
        "stat-card",
        variant === "accent"  && "stat-card--accent",
        variant === "success" && "stat-card--success",
        variant === "danger"  && "stat-card--danger",
        className
      )}
      {...props}
    >
      {/* Label — text-secondary, font-size-xs, uppercase */}
      <span
        data-slot="stat-card-label"
        className="stat-card__label"
      >
        {label}
      </span>

      {/* Value row */}
      <div className="flex items-end gap-2">
        <span
          data-slot="stat-card-value"
          className="stat-card__value"
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
            "stat-card__trend",
            isPositiveDelta  && "stat-card__trend--up",
            isNegativeDelta  && "stat-card__trend--down",
          )}
        >
          {delta}
        </span>
      )}
    </div>
  )
}
