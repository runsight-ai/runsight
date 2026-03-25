import * as React from "react"

import { cn } from "@/utils/helpers"

// Slider pseudo-element styles (cannot be expressed with Tailwind utilities alone).
// These are scoped to [data-slot="slider"] to avoid global bleed.
const sliderPseudoStyles = `
  [data-slot="slider"]::-webkit-slider-thumb {
    appearance: none;
    width: var(--icon-size-md);
    height: var(--icon-size-md);
    background: var(--interactive-default);
    border-radius: var(--radius-full);
    cursor: pointer;
    border: var(--border-width-thick) solid var(--surface-primary);
    box-shadow: var(--elevation-raised-shadow);
    transition: transform var(--duration-100) var(--ease-out);
  }
  [data-slot="slider"]::-webkit-slider-thumb:hover {
    transform: scale(1.15);
  }
  [data-slot="slider"]:focus-visible::-webkit-slider-thumb {
    outline: var(--focus-ring-width) solid var(--focus-ring-color);
    outline-offset: var(--focus-ring-offset);
  }
  [data-slot="slider"]::-moz-range-thumb {
    width: var(--icon-size-md);
    height: var(--icon-size-md);
    background: var(--interactive-default);
    border-radius: var(--radius-full);
    cursor: pointer;
    border: var(--border-width-thick) solid var(--surface-primary);
    box-shadow: var(--elevation-raised-shadow);
    transition: transform var(--duration-100) var(--ease-out);
  }
  [data-slot="slider"]::-moz-range-thumb:hover {
    transform: scale(1.15);
  }
`

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
      <>
        <style>{sliderPseudoStyles}</style>
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
          className={cn(
            // Reset
            "appearance-none",
            // Track layout
            "w-full h-1",
            // Track surface & shape
            "bg-neutral-5 rounded-full",
            // Remove default outline (pseudo-element handles focus ring)
            "outline-none",
            // Cursor
            "cursor-pointer",
            // Disabled
            "disabled:opacity-50 disabled:cursor-not-allowed",
            className
          )}
          {...props}
        />
      </>
    )
  }
)

Slider.displayName = "Slider"

export { Slider }
