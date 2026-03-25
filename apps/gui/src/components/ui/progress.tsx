import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/utils/helpers"

// Design system tokens: neutral-3 (track), interactive-default (default fill),
// success-9 (success), danger-9 (danger), radius-full
const progressTrackVariants = cva(
  "relative w-full overflow-hidden rounded-radius-full bg-neutral-3",
  {
    variants: {
      variant: {
        default: "h-2",
        md: "h-2",
        success: "h-2",
        danger: "h-2",
        indeterminate: "h-2",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

const progressFillVariants = cva(
  "h-full rounded-radius-full transition-all duration-300",
  {
    variants: {
      variant: {
        default: "bg-interactive-default",
        md: "bg-interactive-default",
        success: "bg-success-9",
        danger: "bg-danger-9",
        indeterminate: "bg-interactive-default animate-[indeterminate_1.5s_ease-in-out_infinite]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

interface ProgressProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof progressTrackVariants> {
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
      className={cn(progressTrackVariants({ variant }), className)}
      {...props}
    >
      <div
        data-slot="progress-fill"
        className={cn(progressFillVariants({ variant }))}
        style={
          isIndeterminate
            ? { width: "40%", position: "absolute" }
            : { width: `${clampedValue}%` }
        }
      />
    </div>
  )
}

export { Progress, progressTrackVariants, progressFillVariants }
