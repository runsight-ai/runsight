import * as React from "react"

import { cn } from "@/utils/helpers"

// Design system tokens: neutral-3 (background), neutral-4 (shimmer), shimmer/pulse animation

// Variant → BEM modifier map
const skeletonVariants = {
  text: "skeleton--text",
  "text-sm": "skeleton--text-sm",
  heading: "skeleton--heading",
  avatar: "skeleton--avatar",
  button: "skeleton--button",
} as const

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: keyof typeof skeletonVariants
}

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
      className={cn(
        "skeleton",
        skeletonVariants[variant ?? "text"],
        className
      )}
      {...props}
    />
  )
}

export { Skeleton }
