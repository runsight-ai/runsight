"use client"

import * as React from "react"

import { cn } from "@/utils/helpers"

// Design system tokens: font-size-sm, font-weight-medium, text-secondary
// field__label BEM class handles all visual styling
// field__label--required applies a red asterisk via CSS ::after

interface LabelProps extends React.ComponentProps<"label"> {
  /** Adds a visual asterisk (field__label--required BEM modifier) */
  required?: boolean
}

function Label({ className, required, ...props }: LabelProps) {
  return (
    <label
      data-slot="label"
      className={cn(
        "field__label",
        required && "field__label--required",
        "group-data-[disabled=true]:pointer-events-none group-data-[disabled=true]:opacity-50",
        "peer-disabled:cursor-not-allowed peer-disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
}

export { Label }
