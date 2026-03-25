import * as React from "react"
import { Input as InputPrimitive } from "@base-ui/react/input"

import { cn } from "@/utils/helpers"

// Design system tokens: control-height-sm, font-size-md, border-default, border-focus, surface-tertiary
function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <InputPrimitive
      type={type}
      data-slot="input"
      className={cn(
        "h-control-height-sm w-full min-w-0 rounded-radius-md border border-border-default bg-surface-tertiary px-2.5 py-1 text-font-size-md text-heading transition-colors outline-none",
        "placeholder:text-muted",
        "hover:border-border-hover",
        "focus-visible:border-border-focus focus-visible:ring-3 focus-visible:ring-border-focus/50",
        "disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
        "aria-invalid:border-danger-9 aria-invalid:ring-3 aria-invalid:ring-danger-9/20",
        "file:inline-flex file:h-6 file:border-0 file:text-font-size-sm file:font-weight-medium file:text-primary",
        className
      )}
      {...props}
    />
  )
}

export { Input }
