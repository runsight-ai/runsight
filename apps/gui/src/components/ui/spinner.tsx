import * as React from "react"

import { cn } from "@/utils/helpers"

// Design system tokens: icon-size-sm, icon-size-md, icon-size-xl,
// text-muted, interactive-default, border-width-thick, radius-full

// Size → BEM modifier map
const sizeVariants = {
  sm: "spinner--sm",
  md: "spinner--md",
  lg: "spinner--lg",
} as const

// Visual variant → BEM modifier map
const visualVariants = {
  default: "",
  accent: "spinner--accent",
} as const

interface SpinnerProps extends React.HTMLAttributes<HTMLDivElement> {
  size?: keyof typeof sizeVariants
  variant?: keyof typeof visualVariants
}

function Spinner({
  className,
  size = "md",
  variant = "default",
  ...props
}: SpinnerProps) {
  return (
    <div
      role="status"
      aria-label="Loading"
      data-slot="spinner"
      className={cn(
        "spinner",
        sizeVariants[size ?? "md"],
        visualVariants[variant ?? "default"],
        className
      )}
      {...props}
    >
      <span className="spinner__circle" />
    </div>
  )
}

export { Spinner }
