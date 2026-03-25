import * as React from "react"

import { cn } from "@/utils/helpers"

// Design system tokens: control-height-sm, font-size-md, border-default, border-focus, surface-tertiary
function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex field-sizing-content min-h-control-height-sm w-full rounded-radius-md border border-border-default bg-surface-tertiary px-2.5 py-2 text-font-size-md text-heading transition-colors outline-none resize-vertical",
        "placeholder:text-muted",
        "hover:border-border-hover",
        "focus-visible:border-border-focus focus-visible:ring-3 focus-visible:ring-border-focus/50",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "aria-invalid:border-danger-9 aria-invalid:ring-3 aria-invalid:ring-danger-9/20",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
