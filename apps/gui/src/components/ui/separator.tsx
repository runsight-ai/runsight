"use client"

import { Separator as SeparatorPrimitive } from "@base-ui/react/separator"

import { cn } from "@/utils/helpers"

// Design system tokens: border-subtle
// divider BEM classes handle: divider--horizontal, divider--vertical using border-subtle

function Separator({
  className,
  orientation = "horizontal",
  ...props
}: SeparatorPrimitive.Props) {
  return (
    <SeparatorPrimitive
      data-slot="separator"
      orientation={orientation}
      className={cn(
        "divider",
        orientation === "horizontal" ? "divider--horizontal" : "divider--vertical",
        className
      )}
      {...props}
    />
  )
}

export { Separator }
