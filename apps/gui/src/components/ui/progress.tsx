import * as React from "react"

import { cn } from "@/utils/helpers"

// Design system tokens: neutral-3 (track), interactive-default (default fill),
// success-9 (success fill), danger-9 (danger fill), radius-full

// Variant → BEM modifier map
const progressVariants = {
  default: "",
  md: "progress--md",
  success: "progress--success",
  danger: "progress--danger",
  indeterminate: "progress--indeterminate",
} as const

interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: keyof typeof progressVariants
  value?: number
}

function Progress({
  className,
  variant = "default",
  value = 0,
  ...props
}: ProgressProps) {
  const isIndeterminate = variant === "indeterminate"
  const clampedValue = Math.max(0, Math.min(100, value ?? 0))

  return (
    <div
      role="progressbar"
      aria-valuenow={isIndeterminate ? undefined : clampedValue}
      aria-valuemin={0}
      aria-valuemax={100}
      data-slot="progress"
      className={cn(
        "progress",
        progressVariants[variant ?? "default"],
        className
      )}
      {...props}
    >
      <div
        data-slot="progress-fill"
        className="progress__fill"
        style={
          isIndeterminate
            ? undefined
            : { width: `${clampedValue}%` }
        }
      />
    </div>
  )
}

export { Progress }
