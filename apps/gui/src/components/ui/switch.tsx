import * as React from "react"
import { Switch as SwitchPrimitive } from "@base-ui/react/switch"

import { cn } from "@/utils/helpers"

// Design tokens: neutral-5 (track off), interactive-default (track on),
// neutral-12 (thumb off), text-on-accent (thumb on)

interface SwitchProps extends SwitchPrimitive.Root.Props {
  /** Optional visible label text */
  label?: React.ReactNode
  /** Additional className applied to the outer wrapper */
  wrapperClassName?: string
}

function Switch({ className, label, wrapperClassName, ...props }: SwitchProps) {
  return (
    <label
      data-slot="switch-wrapper"
      className={cn(
        "relative inline-flex items-center gap-2 cursor-pointer select-none",
        wrapperClassName
      )}
    >
      <SwitchPrimitive.Root
        data-slot="switch"
        className={cn(
          // Track: base layout
          "w-9 h-5 relative flex-shrink-0",
          // Track: shape & surface (off state)
          "bg-neutral-5 border border-border-default rounded-full",
          // Track: transitions
          "transition-[background,border-color] duration-150 ease-default",
          // Track: checked (on) state — base-ui sets data-checked
          "data-[checked]:bg-interactive-default data-[checked]:border-interactive-default",
          // Track: focus ring
          "focus-visible:outline focus-visible:outline-[var(--focus-ring-width)] focus-visible:outline-[var(--focus-ring-color)] focus-visible:outline-offset-[var(--focus-ring-offset)]",
          // Track: disabled state
          "data-[disabled]:opacity-50 data-[disabled]:cursor-not-allowed",
          className
        )}
        {...props}
      >
        <SwitchPrimitive.Thumb
          data-slot="switch-thumb"
          className={cn(
            // Thumb: position & size
            "absolute top-0.5 left-0.5 w-3.5 h-3.5",
            // Thumb: shape & surface (off state)
            "bg-neutral-12 rounded-full",
            // Thumb: transition
            "transition-transform duration-150 ease-[var(--ease-spring)]",
            // Thumb: checked state — translate to the right (track 36px, thumb 14px → 16px gap)
            "data-[checked]:translate-x-4 data-[checked]:bg-text-on-accent"
          )}
        />
      </SwitchPrimitive.Root>
      {label && (
        <span
          data-slot="switch-label"
          className="text-md text-primary"
        >
          {label}
        </span>
      )}
    </label>
  )
}

export { Switch }
