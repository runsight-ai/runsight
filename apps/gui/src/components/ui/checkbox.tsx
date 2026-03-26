import * as React from "react"

import { cn } from "@/utils/helpers"

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

    const visual = (
      <span className="relative flex-shrink-0">
        {/* Visually hidden input — drives all peer-* states */}
        <input
          type="checkbox"
          ref={resolvedRef}
          disabled={disabled}
          data-slot="checkbox"
          className={cn("peer sr-only", className)}
          {...props}
        />
        {/* Visual box */}
        <span
          className={[
            "block w-4 h-4 rounded-xs border border-border-default bg-surface-primary",
            "transition-[background,border-color] duration-100 ease-default",
            "peer-hover:border-border-hover",
            "peer-checked:bg-interactive-default peer-checked:border-interactive-default",
            "peer-indeterminate:bg-interactive-default peer-indeterminate:border-interactive-default",
            "peer-focus-visible:outline peer-focus-visible:outline-[var(--focus-ring-width)]",
            "peer-focus-visible:outline-[var(--focus-ring-color)] peer-focus-visible:outline-offset-[var(--focus-ring-offset)]",
            "peer-disabled:opacity-50 peer-disabled:cursor-not-allowed",
          ].join(" ")}
        />
        {/* Checkmark — visible when checked */}
        <svg
          className="absolute inset-0 m-auto w-3 h-3 pointer-events-none opacity-0 peer-checked:opacity-100 text-on-accent"
          viewBox="0 0 12 12"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <polyline points="2.5 6 5 8.5 9.5 3.5" />
        </svg>
        {/* Indeterminate dash — visible when indeterminate */}
        <span
          className="absolute top-[7px] left-[3px] w-[10px] h-[2px] bg-on-accent pointer-events-none opacity-0 peer-indeterminate:opacity-100"
          aria-hidden="true"
        />
      </span>
    )

    if (label) {
      return (
        <label className="inline-flex items-center gap-2 cursor-pointer select-none">
          {visual}
          <span className="text-md text-primary">{label}</span>
        </label>
      )
    }

    return (
      <label className="inline-flex items-center cursor-pointer select-none">
        {visual}
      </label>
    )
  }
)

Checkbox.displayName = "Checkbox"

export { Checkbox }
