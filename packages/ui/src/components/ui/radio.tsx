import * as React from "react"

import { cn } from "../../utils/helpers"

// Radio input base classes
const radioInputClasses = [
  // Reset
  "appearance-none",
  // Dimensions: icon-size-md = 1rem (16px)
  "w-4 h-4",
  // Border & shape: radius-full = rounded-full
  "border border-border-default rounded-full",
  // Surface
  "bg-surface-primary",
  // Cursor & layout
  "cursor-pointer flex-shrink-0 relative",
  // Transitions
  "transition-[background,border-color] duration-100 ease-default",
  // Hover
  "hover:border-border-hover",
  // Checked state: show border color only (dot via after)
  "checked:border-interactive-default",
  // Checked dot via after pseudo-element
  "checked:after:content-[''] checked:after:absolute checked:after:top-[3px] checked:after:left-[3px]",
  "checked:after:w-[8px] checked:after:h-[8px]",
  "checked:after:rounded-full checked:after:bg-interactive-default",
  // Focus ring
  "focus-visible:outline focus-visible:outline-[var(--focus-ring-width)] focus-visible:outline-[var(--focus-ring-color)] focus-visible:outline-offset-[var(--focus-ring-offset)]",
  // Disabled
  "disabled:opacity-50 disabled:cursor-not-allowed",
].join(" ")

// ---------------------------------------------------------------------------
// Radio — single radio input
// ---------------------------------------------------------------------------

export interface RadioProps
  extends Omit<React.ComponentProps<"input">, "type"> {
  label?: string
}

const Radio = React.forwardRef<HTMLInputElement, RadioProps>(
  ({ className, disabled, label, ...props }, ref) => {
    if (label) {
      return (
        <label className="inline-flex items-center gap-2 cursor-pointer select-none">
          <input
            type="radio"
            ref={ref}
            disabled={disabled}
            data-slot="radio"
            className={cn(radioInputClasses, className)}
            {...props}
          />
          <span className="text-md text-primary">{label}</span>
        </label>
      )
    }

    return (
      <input
        type="radio"
        ref={ref}
        disabled={disabled}
        data-slot="radio"
        className={cn(radioInputClasses, className)}
        {...props}
      />
    )
  }
)

Radio.displayName = "Radio"

// ---------------------------------------------------------------------------
// RadioGroup — container supporting vertical (default) and horizontal layout
// ---------------------------------------------------------------------------

export interface RadioGroupProps extends React.ComponentProps<"div"> {
  orientation?: "vertical" | "horizontal"
}

function RadioGroup({
  className,
  orientation = "vertical",
  ...props
}: RadioGroupProps) {
  return (
    <div
      role="radiogroup"
      data-slot="radio-group"
      data-orientation={orientation}
      className={cn(
        "flex flex-col gap-2",
        orientation === "horizontal" && "flex-row gap-4",
        className
      )}
      {...props}
    />
  )
}

export { Radio, RadioGroup }
