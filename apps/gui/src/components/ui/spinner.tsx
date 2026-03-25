import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/utils/helpers"

// Design system tokens: icon-size-sm (14px), icon-size-md (16px), icon-size-xl (24px),
// text-muted, interactive-default, border-width-thick (2px), radius-full

const spinnerVariants = cva(
  "inline-flex items-center justify-center text-muted",
  {
    variants: {
      variant: {
        default: "",
        accent: "text-interactive-default",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

// Circle size classes keyed by size — maps to icon-size tokens
const circleSize = {
  sm: "w-[14px] h-[14px]",  // icon-size-sm
  md: "w-[16px] h-[16px]",  // icon-size-md
  lg: "w-[24px] h-[24px]",  // icon-size-xl
} as const

type SpinnerSize = keyof typeof circleSize

interface SpinnerProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof spinnerVariants> {
  size?: SpinnerSize
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
      className={cn(spinnerVariants({ variant }), className)}
      {...props}
    >
      <span
        className={cn(
          // border-width-thick = 2px, transparent right border creates spinner gap
          "block border-2 border-current border-r-transparent rounded-full animate-spin",
          circleSize[size ?? "md"]
        )}
      />
    </div>
  )
}

export { Spinner }
