import * as React from "react"

import { cn } from "@/utils/helpers"

// Design system tokens: icon-size-xs (12px), icon-size-sm (14px), icon-size-md (16px),
// icon-size-lg (20px), icon-size-xl (24px)
// SVG inherits stroke: currentColor, fill: none, stroke-width: 1.5

const sizeVariants = {
  xs: "icon--xs",
  sm: "icon--sm",
  md: "icon--md",
  lg: "icon--lg",
  xl: "icon--xl",
} as const

type IconSize = keyof typeof sizeVariants

interface IconProps extends React.HTMLAttributes<HTMLSpanElement> {
  size?: IconSize
  /** Decorative icons should be aria-hidden on the parent or pass aria-hidden */
  "aria-hidden"?: boolean | "true" | "false"
}

function Icon({
  className,
  size = "md",
  children,
  ...props
}: IconProps) {
  return (
    <span
      data-slot="icon"
      className={cn(
        "icon",
        sizeVariants[size],
        className
      )}
      {...props}
    >
      {children}
    </span>
  )
}

export { Icon }
export type { IconSize, IconProps }
