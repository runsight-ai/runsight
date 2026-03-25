import * as React from "react"

import { cn } from "@/utils/helpers"

export interface CheckboxProps
  extends Omit<React.ComponentProps<"input">, "type"> {
  indeterminate?: boolean
  label?: string
}

const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, indeterminate = false, disabled, ...props }, ref) => {
    const innerRef = React.useRef<HTMLInputElement>(null)
    const resolvedRef = (ref as React.RefObject<HTMLInputElement>) ?? innerRef

    React.useEffect(() => {
      if (resolvedRef.current) {
        resolvedRef.current.indeterminate = indeterminate
      }
    }, [indeterminate, resolvedRef])

    return (
      <input
        type="checkbox"
        ref={resolvedRef}
        disabled={disabled}
        data-slot="checkbox"
        className={cn(
          // Layout & shape
          "size-4 shrink-0 cursor-pointer appearance-none rounded-radius-xs border border-border-default bg-surface-primary",
          // Checked state: interactive-default fill
          "checked:border-interactive-default checked:bg-interactive-default",
          // Indeterminate state
          "indeterminate:border-interactive-default indeterminate:bg-interactive-default",
          // Focus ring
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus/50 focus-visible:border-ring",
          // Disabled
          "disabled:cursor-not-allowed disabled:opacity-50",
          className
        )}
        {...props}
      />
    )
  }
)

Checkbox.displayName = "Checkbox"

export { Checkbox }
