"use client"

import * as React from "react"

import { cn } from "@/utils/helpers"

// Design system tokens: font-size-sm, font-weight-medium, text-secondary
// field__label BEM class handles all visual styling

function Label({ className, ...props }: React.ComponentProps<"label">) {
  return (
    <label
      data-slot="label"
      className={cn(
        "field__label",
        "group-data-[disabled=true]:pointer-events-none group-data-[disabled=true]:opacity-50",
        "peer-disabled:cursor-not-allowed peer-disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
}

export { Label }
