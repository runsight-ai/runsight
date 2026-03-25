import * as React from "react"

import { cn } from "@/utils/helpers"

// Design tokens: surface-primary (bg), border-default (border), radius-full (circular),
// interactive-default (selected state), text-on-accent (dot indicator)

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
        <label className="radio">
          <input
            type="radio"
            ref={ref}
            disabled={disabled}
            data-slot="radio"
            className={cn("radio__input", className)}
            {...props}
          />
          <span className="radio__label">{label}</span>
        </label>
      )
    }

    return (
      <input
        type="radio"
        ref={ref}
        disabled={disabled}
        data-slot="radio"
        className={cn("radio__input", className)}
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
        "radio-group",
        orientation === "horizontal" && "radio-group--horizontal",
        className
      )}
      {...props}
    />
  )
}

export { Radio, RadioGroup }
