import * as React from "react"

import { cn } from "@/utils/helpers"

// ---------------------------------------------------------------------------
// Radio — single radio input
// ---------------------------------------------------------------------------

export interface RadioProps
  extends Omit<React.ComponentProps<"input">, "type"> {
  label?: string
}

const Radio = React.forwardRef<HTMLInputElement, RadioProps>(
  ({ className, disabled, ...props }, ref) => {
    return (
      <input
        type="radio"
        ref={ref}
        disabled={disabled}
        data-slot="radio"
        className={cn(
          // Layout & shape — radius-full for circular appearance
          "size-4 shrink-0 cursor-pointer appearance-none rounded-radius-full border border-border-default bg-surface-primary",
          // Checked state: interactive-default fill
          "checked:border-interactive-default checked:bg-interactive-default",
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
        "flex gap-2",
        orientation === "vertical" ? "flex-col" : "flex-row inline-flex",
        className
      )}
      {...props}
    />
  )
}

export { Radio, RadioGroup }
