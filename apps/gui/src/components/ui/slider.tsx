import * as React from "react"

import { cn } from "@/utils/helpers"

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
      <div
        data-slot="slider"
        className={cn(
          "relative flex w-full touch-none select-none items-center",
          disabled && "cursor-not-allowed opacity-50",
          className
        )}
      >
        {/*
         * Track background: surface-tertiary (neutral-5 as fallback)
         * Fill: interactive-default
         * Thumb: neutral-12 with elevation-raised-shadow, radius-full
         */}
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
          data-slot="slider-input"
          className={cn(
            // Reset native appearance
            "w-full cursor-pointer appearance-none bg-transparent outline-none",
            // Track — surface-tertiary background, neutral-5 height via CSS
            "[&::-webkit-slider-runnable-track]:h-1.5 [&::-webkit-slider-runnable-track]:rounded-radius-full [&::-webkit-slider-runnable-track]:bg-surface-tertiary [&::-webkit-slider-runnable-track]:bg-neutral-5",
            // Track fill — interactive-default accent
            "[&::-webkit-slider-runnable-track]:accent-[var(--interactive-default,theme(colors.blue.600))]",
            // Firefox track
            "[&::-moz-range-track]:h-1.5 [&::-moz-range-track]:rounded-radius-full [&::-moz-range-track]:bg-surface-tertiary",
            // Firefox progress fill
            "[&::-moz-range-progress]:bg-interactive-default",
            // Thumb — neutral-12, radius-full, elevation-raised-shadow
            "[&::-webkit-slider-thumb]:-mt-[5px] [&::-webkit-slider-thumb]:size-4 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-radius-full [&::-webkit-slider-thumb]:bg-neutral-12 [&::-webkit-slider-thumb]:shadow-elevation-raised-shadow [&::-webkit-slider-thumb]:transition-shadow",
            "[&::-moz-range-thumb]:size-4 [&::-moz-range-thumb]:appearance-none [&::-moz-range-thumb]:rounded-radius-full [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:bg-neutral-12 [&::-moz-range-thumb]:shadow-elevation-raised-shadow",
            // Focus
            "focus-visible:[&::-webkit-slider-thumb]:ring-2 focus-visible:[&::-webkit-slider-thumb]:ring-border-focus/50",
            // Disabled
            "disabled:pointer-events-none",
          )}
          {...props}
        />
      </div>
    )
  }
)

Slider.displayName = "Slider"

export { Slider }
