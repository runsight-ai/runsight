import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/utils/helpers"

// Design system tokens: icon-size-sm, icon-size-md, icon-size-xl,
// text-muted, interactive-default, border-width-thick, radius-full
const spinnerVariants = cva(
  "animate-spin rounded-radius-full border-border-width-thick border-transparent",
  {
    variants: {
      size: {
        sm: "size-[--icon-size-sm]",
        md: "size-[--icon-size-md]",
        lg: "size-[--icon-size-xl]",
      },
      variant: {
        default: "border-t-text-muted",
        accent: "border-t-interactive-default",
      },
    },
    defaultVariants: {
      size: "md",
      variant: "default",
    },
  }
)

interface SpinnerProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof spinnerVariants> {}

// Inline import to avoid barrel file imports per green-fe-patterns
import * as React from "react"

function Spinner({
  className,
  size = "md",
  variant = "default",
  ...props
}: SpinnerProps) {
  // Size map for inline style (fallback) using design system tokens
  // icon-size-sm=14px, icon-size-md=16px, icon-size-xl=24px
  const sizeStyles: Record<NonNullable<typeof size>, React.CSSProperties> = {
    sm: { width: "var(--icon-size-sm)", height: "var(--icon-size-sm)" },
    md: { width: "var(--icon-size-md)", height: "var(--icon-size-md)" },
    lg: { width: "var(--icon-size-xl)", height: "var(--icon-size-xl)" },
  }

  const variantStyles: Record<NonNullable<typeof variant>, React.CSSProperties> = {
    default: { borderTopColor: "var(--text-muted)" },
    accent: { borderTopColor: "var(--interactive-default)" },
  }

  return (
    <div
      role="status"
      aria-label="Loading"
      data-slot="spinner"
      style={{
        ...sizeStyles[size ?? "md"],
        ...variantStyles[variant ?? "default"],
        borderWidth: "var(--border-width-thick)",
        borderRadius: "var(--radius-full)",
        borderStyle: "solid",
        borderColor: "transparent",
        animation: "spin 1s linear infinite",
      }}
      className={cn(className)}
      {...props}
    />
  )
}

export { Spinner, spinnerVariants }
