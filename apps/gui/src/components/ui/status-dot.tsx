import * as React from "react"

import { cn } from "@/utils/helpers"

// Design system tokens: neutral-9, info-9, success-9, warning-9, danger-9,
// radius-full, space-2

// Variant → BEM modifier map
const statusDotVariants = {
  neutral: "status-dot--neutral",
  active: "status-dot--active",
  success: "status-dot--success",
  warning: "status-dot--warning",
  danger: "status-dot--danger",
} as const

// Animation → BEM modifier map
const statusDotAnimations = {
  none: "",
  pulse: "status-dot--pulse",
  spin: "status-dot--spin",
} as const

interface StatusDotProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: keyof typeof statusDotVariants
  animate?: keyof typeof statusDotAnimations
}

function StatusDot({
  className,
  variant = "neutral",
  animate = "none",
  ...props
}: StatusDotProps) {
  return (
    <span
      data-slot="status-dot"
      className={cn(
        "status-dot",
        statusDotVariants[variant ?? "neutral"],
        statusDotAnimations[animate ?? "none"],
        className
      )}
      {...props}
    />
  )
}

export { StatusDot }
