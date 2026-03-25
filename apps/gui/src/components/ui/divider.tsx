import * as React from "react"

import { cn } from "@/utils/helpers"

// Design system tokens:
// .divider: border: none, margin: 0
// .divider--horizontal: height border-width-thin, background border-subtle, width 100%
// .divider--vertical: width border-width-thin, background border-subtle, align-self stretch
//
// Note: separator.tsx remains for backward compat; this is the canonical DS divider.

type DividerOrientation = "horizontal" | "vertical"

interface DividerProps extends React.HTMLAttributes<HTMLDivElement> {
  orientation?: DividerOrientation
}

function Divider({
  className,
  orientation = "horizontal",
  ...props
}: DividerProps) {
  return (
    <div
      role="separator"
      aria-orientation={orientation}
      data-slot="divider"
      className={cn(
        "divider",
        orientation === "horizontal" ? "divider--horizontal" : "divider--vertical",
        className
      )}
      {...props}
    />
  )
}

export { Divider }
export type { DividerOrientation, DividerProps }
