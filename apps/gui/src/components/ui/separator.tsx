"use client"

import { Separator as SeparatorPrimitive } from "@base-ui/react/separator"

import { cn } from "@/utils/helpers"

// .divider--horizontal: height 1px, bg border-subtle, width 100%
// .divider--vertical: width 1px, bg border-subtle, align-self stretch

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
        "border-none m-0",
        orientation === "horizontal"
          ? "h-px w-full bg-border-subtle"
          : "w-px self-stretch bg-border-subtle",
        className
      )}
      {...props}
    />
  )
}

export { Separator }
