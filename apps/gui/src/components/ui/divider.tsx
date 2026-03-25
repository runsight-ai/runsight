import { cva, type VariantProps } from "class-variance-authority"
import * as React from "react"

import { cn } from "@/utils/helpers"

// .divider: border none, margin 0
// .divider--horizontal: height 1px (border-width-thin), bg border-subtle, width 100%
// .divider--vertical: width 1px (border-width-thin), bg border-subtle, align-self stretch
//
// Note: separator.tsx remains for backward compat; this is the canonical DS divider.

const dividerVariants = cva("border-none m-0 bg-border-subtle", {
  variants: {
    orientation: {
      horizontal: "h-px w-full",
      vertical:   "w-px self-stretch",
    },
  },
  defaultVariants: {
    orientation: "horizontal",
  },
})

type DividerOrientation = NonNullable<VariantProps<typeof dividerVariants>["orientation"]>

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
      className={cn(dividerVariants({ orientation }), className)}
      {...props}
    />
  )
}

export { Divider, dividerVariants }
export type { DividerOrientation, DividerProps }
