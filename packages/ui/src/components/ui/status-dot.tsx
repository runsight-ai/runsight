import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "../../utils/helpers"

// Design system tokens: space-2=8px (w-2 h-2), radius-full, flex-shrink-0
// neutral-9, info-9, success-9, danger-9, warning-9
// pulse @keyframes: opacity 1→0.5→1 over 2s (globals.css)
// spin @keyframes: rotate 0→360 over 1s (globals.css)
// spin variant overrides shape: border-width-thick (2px), border-r-transparent, no bg

const statusDotVariants = cva(
  // Base: space-2 = 8px square, radius-full, flex-shrink-0
  "w-2 h-2 rounded-full shrink-0",
  {
    variants: {
      variant: {
        neutral: "bg-neutral-9",
        active:  "bg-info-9",
        success: "bg-success",
        warning: "bg-warning",
        danger:  "bg-danger",
      },
      animate: {
        none: "",
        // pulse: opacity oscillation (2s ease-in-out infinite)
        pulse: "animate-pulse",
        // spin: becomes a spinner ring — reset radius, transparent bg, border
        spin: "rounded-none bg-transparent border-2 border-current border-r-transparent animate-spin",
      },
    },
    defaultVariants: {
      variant: "neutral",
      animate: "none",
    },
  }
)

interface StatusDotProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof statusDotVariants> {}

function StatusDot({
  className,
  variant = "neutral",
  animate = "none",
  ...props
}: StatusDotProps) {
  return (
    <span
      data-slot="status-dot"
      className={cn(statusDotVariants({ variant, animate }), className)}
      {...props}
    />
  )
}

export { StatusDot }
