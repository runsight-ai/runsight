"use client"

import { Separator as SeparatorPrimitive } from "@base-ui/react/separator"

import { cn } from "@/utils/helpers"

// Design system tokens: border-subtle
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
        "shrink-0 border-border-subtle data-horizontal:h-px data-horizontal:w-full data-horizontal:border-t data-vertical:w-px data-vertical:self-stretch data-vertical:border-l",
        className
      )}
      {...props}
    />
  )
}

export { Separator }
