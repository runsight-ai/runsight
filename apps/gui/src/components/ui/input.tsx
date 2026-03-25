import * as React from "react"
import { Input as InputPrimitive } from "@base-ui/react/input"

import { cn } from "@/utils/helpers"

// Design tokens: control-height-sm (height), font-size-md (text), surface-tertiary (bg),
// border-default (border), border-focus (focus ring), text-heading (color), text-muted (placeholder),
// border-border-default (base border)
export interface InputProps extends React.ComponentProps<"input"> {
  size?: "xs" | "md" | "lg"
  error?: boolean
}

function Input({ className, type, size, error, readOnly, disabled, ...props }: InputProps) {
  return (
    <InputPrimitive
      type={type}
      data-slot="input"
      readOnly={readOnly}
      disabled={disabled}
      className={cn(
        "input",
        error && "input--error",
        disabled && "input--disabled",
        readOnly && "input--readonly",
        size === "xs" && "input--xs",
        size === "md" && "input--md",
        size === "lg" && "input--lg",
        className
      )}
      {...props}
    />
  )
}

export { Input }
