"use client"

import * as React from "react"

import { cn } from "../../utils/helpers"

// .field__label: font-size-sm, font-weight-medium, text-primary
// .field__label--required::after: content ' *', color danger-9
// Requirement asterisk is rendered as inline JSX to avoid needing CSS ::after

interface LabelProps extends React.ComponentProps<"label"> {
  /** Adds a visual asterisk after the label text */
  required?: boolean
}

function Label({ className, required, children, ...props }: LabelProps) {
  return (
    <label
      data-slot="label"
      className={cn(
        "text-sm font-medium text-primary",
        "group-data-[disabled=true]:pointer-events-none group-data-[disabled=true]:opacity-50",
        "peer-disabled:cursor-not-allowed peer-disabled:opacity-50",
        className
      )}
      {...props}
    >
      {children}
      {required && (
        <span aria-hidden="true" className="ml-0.5 text-danger-9">
          {" *"}
        </span>
      )}
    </label>
  )
}

export { Label }
