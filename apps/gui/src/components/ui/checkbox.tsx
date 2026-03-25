import * as React from "react"

import { cn } from "@/utils/helpers"

// Design tokens: surface-primary (bg), border-default (border), radius-xs (corners),
// interactive-default (checked state), text-on-accent (check icon)
export interface CheckboxProps
  extends Omit<React.ComponentProps<"input">, "type"> {
  indeterminate?: boolean
  label?: string
}

const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, indeterminate = false, disabled, label, ...props }, ref) => {
    const innerRef = React.useRef<HTMLInputElement>(null)
    const resolvedRef = (ref as React.RefObject<HTMLInputElement>) ?? innerRef

    React.useEffect(() => {
      if (resolvedRef.current) {
        resolvedRef.current.indeterminate = indeterminate
      }
    }, [indeterminate, resolvedRef])

    if (label) {
      return (
        <label className="checkbox">
          <input
            type="checkbox"
            ref={resolvedRef}
            disabled={disabled}
            data-slot="checkbox"
            className={cn("checkbox__input", className)}
            {...props}
          />
          <span className="checkbox__label">{label}</span>
        </label>
      )
    }

    return (
      <input
        type="checkbox"
        ref={resolvedRef}
        disabled={disabled}
        data-slot="checkbox"
        className={cn("checkbox__input", className)}
        {...props}
      />
    )
  }
)

Checkbox.displayName = "Checkbox"

export { Checkbox }
