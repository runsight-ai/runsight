import * as React from "react"

import { cn } from "@/utils/helpers"

// Checkbox input base classes
const checkboxInputClasses = [
  // Reset
  "appearance-none",
  // Dimensions: icon-size-md = 1rem (16px)
  "w-4 h-4",
  // Border & shape
  "border border-border-default rounded-xs",
  // Surface
  "bg-surface-primary",
  // Cursor & layout
  "cursor-pointer flex-shrink-0 relative",
  // Transitions
  "transition-[background,border-color] duration-100 ease-default",
  // Hover
  "hover:border-border-hover",
  // Checked state
  "checked:bg-interactive-default checked:border-interactive-default",
  // Checked checkmark via after pseudo-element
  "checked:after:content-[''] checked:after:absolute checked:after:left-[4px] checked:after:top-[1px]",
  "checked:after:w-[6px] checked:after:h-[10px]",
  "checked:after:border-text-on-accent checked:after:border-solid",
  "checked:after:border-0 checked:after:border-r-[var(--border-width-thick)] checked:after:border-b-[var(--border-width-thick)]",
  "checked:after:rotate-45",
  // Indeterminate state
  "indeterminate:bg-interactive-default indeterminate:border-interactive-default",
  "indeterminate:after:content-[''] indeterminate:after:absolute indeterminate:after:left-[3px] indeterminate:after:top-[6px]",
  "indeterminate:after:w-[8px] indeterminate:after:h-[var(--border-width-thick)]",
  "indeterminate:after:bg-text-on-accent",
  // Focus ring
  "focus-visible:outline focus-visible:outline-[var(--focus-ring-width)] focus-visible:outline-[var(--focus-ring-color)] focus-visible:outline-offset-[var(--focus-ring-offset)]",
  // Disabled
  "disabled:opacity-50 disabled:cursor-not-allowed",
].join(" ")

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
        <label className="inline-flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            ref={resolvedRef}
            disabled={disabled}
            data-slot="checkbox"
            className={cn(checkboxInputClasses, className)}
            {...props}
          />
          <span className="text-md text-primary">{label}</span>
        </label>
      )
    }

    return (
      <input
        type="checkbox"
        ref={resolvedRef}
        disabled={disabled}
        data-slot="checkbox"
        className={cn(checkboxInputClasses, className)}
        {...props}
      />
    )
  }
)

Checkbox.displayName = "Checkbox"

export { Checkbox }
