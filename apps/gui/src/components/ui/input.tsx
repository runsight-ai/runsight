import * as React from "react"
import { Input as InputPrimitive } from "@base-ui/react/input"
import { cva } from "class-variance-authority"

import { cn } from "@/utils/helpers"

const inputVariants = cva(
  [
    // Layout
    "flex items-center gap-2 w-full",
    // Height: default uses control-height-sm (h-8)
    "h-8",
    // Spacing
    "px-2.5",
    // Typography
    "font-body text-md text-heading",
    // Surface & border
    "bg-surface-primary border border-border-default rounded-md",
    // Placeholder
    "placeholder:text-muted",
    // Transitions
    "transition-[border-color,box-shadow] duration-100 ease-default",
    // Hover
    "hover:border-border-hover",
    // Focus
    "focus-within:border-border-focus focus-within:shadow-[0_0_0_var(--space-0-5)_var(--accent-3)] focus-within:outline-none",
    // Disabled
    "disabled:opacity-50 disabled:cursor-not-allowed disabled:bg-surface-secondary",
  ].join(" "),
  {
    variants: {
      error: {
        true: "border-danger-9 focus-within:shadow-[0_0_0_var(--space-0-5)_var(--danger-3)]",
        false: "",
      },
      readOnly: {
        true: "border-border-subtle bg-surface-secondary hover:border-border-subtle",
        false: "",
      },
      size: {
        xs: "h-[var(--control-height-xs)] text-xs px-2",
        sm: "h-8 text-md px-2.5",
        md: "h-[var(--control-height-md)] text-md px-3",
        lg: "h-[var(--control-height-lg)] text-lg px-4",
      },
    },
    defaultVariants: {
      error: false,
      readOnly: false,
      size: "sm",
    },
  }
)

export interface InputProps extends Omit<React.ComponentProps<"input">, "size"> {
  /** CVA size variant — xs | sm (default) | md | lg */
  size?: "xs" | "sm" | "md" | "lg"
  error?: boolean
}

function Input({
  className,
  type,
  size,
  error,
  readOnly,
  disabled,
  ...props
}: InputProps) {
  return (
    <InputPrimitive
      type={type}
      data-slot="input"
      readOnly={readOnly}
      disabled={disabled}
      className={cn(
        inputVariants({
          error: error ?? false,
          readOnly: readOnly ?? false,
          size: size ?? "sm",
        }),
        className
      )}
      {...props}
    />
  )
}

export { Input }
