import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/utils/helpers"

// Design system tokens: neutral-3 (background), neutral-4 (shimmer), animate (shimmer/pulse)
const skeletonVariants = cva(
  "block animate-pulse rounded-radius-sm",
  {
    variants: {
      variant: {
        text: "h-4 w-full bg-neutral-3",
        "text-sm": "h-3 w-3/4 bg-neutral-3",
        heading: "h-6 w-1/2 bg-neutral-3",
        avatar: "size-10 rounded-radius-full bg-neutral-3",
        button: "h-control-height-sm w-24 rounded-radius-md bg-neutral-3",
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
      style={{
        // Use design tokens inline to ensure shimmer highlight reference
        // neutral-4 shimmer via background gradient
        background: `linear-gradient(90deg, var(--neutral-3) 25%, var(--neutral-4) 50%, var(--neutral-3) 75%)`,
        backgroundSize: "200% 100%",
        animation: "shimmer 1.5s ease-in-out infinite",
      }}
      className={cn(skeletonVariants({ variant }), className)}
      {...props}
    />
  )
}

export { Skeleton, skeletonVariants }
