import * as React from "react"

import { cn } from "../../utils/helpers"

export interface SegmentedControlOption {
  value: string
  label: React.ReactNode
  icon?: React.ReactNode
  disabled?: boolean
  ariaLabel?: string
  dataTestId?: string
}

export interface SegmentedControlProps extends Omit<React.ComponentPropsWithoutRef<"div">, "onChange" | "onClick"> {
  options: readonly SegmentedControlOption[]
  activeToggle: string
  onClick: (value: string) => void
}

function SegmentedControl({
  className,
  options,
  activeToggle,
  onClick,
  ...props
}: SegmentedControlProps) {
  return (
    <div
      data-slot="segmented-control"
      role="group"
      className={cn(
        "inline-flex items-center gap-0.5 rounded-md bg-surface-tertiary p-0.5",
        className
      )}
      {...props}
    >
      {options.map((option) => {
        const isActive = option.value === activeToggle

        return (
          <button
            key={option.value}
            type="button"
            aria-label={option.ariaLabel}
            aria-pressed={isActive}
            disabled={option.disabled}
            data-slot="segmented-control-option"
            data-state={isActive ? "active" : "inactive"}
            data-testid={option.dataTestId}
            className={cn(
              "inline-flex min-w-0 items-center justify-center gap-1.5 rounded-sm px-3 py-0.5",
              "font-body text-sm font-medium whitespace-nowrap",
              "border border-transparent bg-transparent text-secondary",
              "transition-colors duration-100 ease-default",
              "hover:text-primary",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-focus",
              "disabled:cursor-not-allowed disabled:opacity-50",
              "data-[state=active]:bg-surface-primary data-[state=active]:text-heading data-[state=active]:shadow-raised",
            )}
            onClick={() => onClick(option.value)}
          >
            {option.icon ? (
              <span aria-hidden="true" className="inline-flex shrink-0 items-center justify-center text-current">
                {option.icon}
              </span>
            ) : null}
            <span className="truncate">{option.label}</span>
          </button>
        )
      })}
    </div>
  )
}

export { SegmentedControl }
