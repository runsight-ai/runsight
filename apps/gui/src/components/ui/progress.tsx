import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/utils/helpers"

// Design system tokens: neutral-3 (track), interactive-default (fill),
// success-9, danger-9, radius-full, space-1=4px, space-2=8px,
// duration-300, ease-out
// progress-slide @keyframes defined in components.css

const progressVariants = cva(
  // Track: full width, neutral-3 bg, radius-full, overflow-hidden
  "w-full bg-neutral-3 rounded-full overflow-hidden",
  {
    variants: {
      variant: {
        // default height: space-1 = 4px (h-1)
        default: "h-1",
        // md height: space-2 = 8px (h-2)
        md: "h-2",
        // success/danger/indeterminate keep default height
        success: "h-1",
        danger: "h-1",
        indeterminate: "h-2", // reference pairs indeterminate with md height
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

const fillVariants = cva(
  // Fill: full height, radius-full, transition width
  "h-full rounded-full transition-[width] duration-300 ease-out",
  {
    variants: {
      variant: {
        default: "bg-interactive-default",
        md: "bg-interactive-default",
        success: "bg-success",
        danger: "bg-danger",
        // indeterminate: 30% width, progress-slide animation
        indeterminate: "w-[30%] bg-interactive-default [animation:progress-slide_1.5s_ease-in-out_infinite]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

interface ProgressProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof progressVariants> {
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
      className={cn(progressVariants({ variant }), className)}
      {...props}
    >
      <div
        data-slot="progress-fill"
        className={fillVariants({ variant })}
        style={isIndeterminate ? undefined : { width: `${clampedValue}%` }}
      />
    </div>
  )
}

export { Progress }
