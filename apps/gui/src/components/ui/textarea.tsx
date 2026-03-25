import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/utils/helpers"

const textareaVariants = cva(
  [
    // Layout
    "w-full",
    // Min-height: control-height-sm * 3 ≈ 3 × 2rem = 6rem
    "min-h-[calc(var(--control-height-sm)*3)]",
    // Spacing
    "px-2.5 py-2",
    // Typography
    "font-body text-md leading-normal text-heading",
    // Surface & border
    "bg-surface-primary border border-border-default rounded-md",
    // Resize
    "resize-y",
    // Placeholder
    "placeholder:text-muted",
    // Transitions
    "transition-[border-color,box-shadow] duration-100 ease-default",
    // Hover
    "hover:border-border-hover",
    // Focus
    "focus:border-border-focus focus:shadow-[0_0_0_var(--space-0-5)_var(--accent-3)] focus:outline-none",
    // Disabled
    "disabled:opacity-50 disabled:cursor-not-allowed disabled:bg-surface-secondary disabled:resize-none",
  ].join(" "),
  {
    variants: {
      code: {
        true: "font-mono text-sm [tab-size:2]",
        false: "",
      },
      autoResize: {
        true: "resize-none overflow-hidden",
        false: "",
      },
    },
    defaultVariants: {
      code: false,
      autoResize: false,
    },
  }
)

export interface TextareaProps
  extends React.ComponentProps<"textarea">,
    VariantProps<typeof textareaVariants> {
  autoResize?: boolean
}

function Textarea({ className, code, autoResize, ...props }: TextareaProps) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        textareaVariants({ code: code ?? false, autoResize: autoResize ?? false }),
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
