"use client"

import * as React from "react"

import { cn } from "@/utils/helpers"

// Design system tokens: font-size-sm (13px), font-weight-medium (500), text-secondary
function Label({ className, ...props }: React.ComponentProps<"label">) {
  return (
    <label
      data-slot="label"
      className={cn(
        "flex items-center gap-2 text-font-size-sm font-weight-medium text-secondary leading-none select-none",
        "group-data-[disabled=true]:pointer-events-none group-data-[disabled=true]:opacity-50",
        "peer-disabled:cursor-not-allowed peer-disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
}

export { Label }
