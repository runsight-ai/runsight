import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/utils/helpers"

// Design system tokens: neutral-9, info-9, success-9, warning-9, danger-9,
// radius-full, space-2
const statusDotVariants = cva(
  "inline-block rounded-radius-full",
  {
    variants: {
      variant: {
        neutral: "bg-neutral-9",
        active: "bg-info-9",
        success: "bg-success-9",
        warning: "bg-warning-9",
        danger: "bg-danger-9",
      },
      animate: {
        none: "",
        pulse: "animate-pulse",
        spin: "animate-spin",
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
      // size uses space-2 token (8px) for the dot dimensions
      style={{
        width: "var(--space-2)",
        height: "var(--space-2)",
        borderRadius: "var(--radius-full)",
        flexShrink: 0,
      }}
      className={cn(statusDotVariants({ variant, animate }), className)}
      {...props}
    />
  )
}

export { StatusDot, statusDotVariants }
