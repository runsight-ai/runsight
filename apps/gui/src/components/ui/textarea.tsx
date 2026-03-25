import * as React from "react"

import { cn } from "@/utils/helpers"

// Design tokens: control-height-sm (min-height ref), font-size-md (text), surface-tertiary (bg),
// border-default (border), border-focus (focus ring), text-heading (color), text-muted (placeholder),
// border-border-default (base border)
export interface TextareaProps extends React.ComponentProps<"textarea"> {
  code?: boolean
  autoResize?: boolean
}

function Textarea({ className, code, autoResize, ...props }: TextareaProps) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "textarea",
        code && "textarea--code",
        autoResize && "textarea--auto-resize",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
