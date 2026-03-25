import * as React from "react"

import { cn } from "@/utils/helpers"

// Design tokens: neutral-5 (track bg), interactive-default (thumb fill),
// neutral-12 (thumb color), elevation-raised-shadow (thumb shadow), radius-full (thumb shape)
export interface SliderProps
  extends Omit<React.ComponentProps<"input">, "type"> {
  /** Current value (controlled) */
  value?: number
  /** Default value (uncontrolled) */
  defaultValue?: number
  /** Minimum value. Defaults to 0. */
  min?: number
  /** Maximum value. Defaults to 100. */
  max?: number
  /** Step increment. Defaults to 1. */
  step?: number
}

const Slider = React.forwardRef<HTMLInputElement, SliderProps>(
  (
    {
      className,
      disabled,
      min = 0,
      max = 100,
      step = 1,
      ...props
    },
    ref
  ) => {
    return (
      <input
        type="range"
        ref={ref}
        role="slider"
        disabled={disabled}
        min={min}
        max={max}
        step={step}
        aria-valuemin={min}
        aria-valuemax={max}
        data-slot="slider"
        className={cn("slider", className)}
        {...props}
      />
    )
  }
)

Slider.displayName = "Slider"

export { Slider }
