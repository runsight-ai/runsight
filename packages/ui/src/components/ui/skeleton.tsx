import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "../../utils/helpers"

// Design system tokens: neutral-3 (background), neutral-4 (shimmer highlight)
// Shimmer @keyframes defined in globals.css — translateX(-100%) → translateX(100%)
// Sizes: font-size-md=14px, font-size-sm=13px, font-size-xl=18px,
//        control-height-sm=32px, radius-full, radius-md

const skeletonVariants = cva(
  [
    // Base: neutral-3 background, relative + overflow-hidden for ::after shimmer
    "bg-neutral-3 rounded-sm relative overflow-hidden",
    // Shimmer overlay via after pseudo-element
    "after:absolute after:inset-0",
    "after:bg-[linear-gradient(90deg,transparent_0%,var(--neutral-4)_50%,transparent_100%)]",
    "after:[animation:shimmer_1.5s_ease-in-out_infinite]",
  ].join(" "),
  {
    variants: {
      variant: {
        // font-size-md = 14px height
        text: "h-[14px] w-[80%]",
        // font-size-sm = 13px height
        "text-sm": "h-[13px] w-[60%]",
        // font-size-xl = 18px height
        heading: "h-[18px] w-[40%]",
        // control-height-sm = 32px, radius-full
        avatar: "w-8 h-8 rounded-full",
        // control-height-sm = 32px height, 100px width, radius-md
        button: "h-8 w-[100px] rounded-md",
      },
    },
    defaultVariants: {
      variant: "text",
    },
  }
)

interface SkeletonProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof skeletonVariants> {}

function Skeleton({
  className,
  variant = "text",
  ...props
}: SkeletonProps) {
  return (
    <div
      data-slot="skeleton"
      aria-busy="true"
      aria-label="Loading"
      className={cn(skeletonVariants({ variant }), className)}
      {...props}
    />
  )
}

export { Skeleton }
