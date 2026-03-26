import * as React from "react"

import { cn } from "@/utils/helpers"
import { Label } from "@/components/ui/label"

// .field: display flex, flex-direction column, gap space-1
// .field__helper: font-size-xs, text-muted
// .field__error: font-size-xs, text-danger-11, flex, items-center, gap-1

function Field({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="field"
      className={cn("flex flex-col gap-1", className)}
      {...props}
    />
  )
}

// FieldLabel is a convenience re-export of Label for field context.
// Consumers can use Label directly if preferred.
const FieldLabel = Label

function FieldHelper({ className, ...props }: React.ComponentProps<"span">) {
  return (
    <span
      data-slot="field-helper"
      className={cn("text-xs text-muted", className)}
      {...props}
    />
  )
}

function FieldError({ className, ...props }: React.ComponentProps<"span">) {
  return (
    <span
      data-slot="field-error"
      className={cn("text-xs text-danger-11 flex items-center gap-1", className)}
      {...props}
    />
  )
}

export { Field, FieldLabel, FieldHelper, FieldError }
