import * as React from "react"
import { Switch as SwitchPrimitive } from "@base-ui/react/switch"

import { cn } from "@/utils/helpers"

// Design tokens: neutral-5 (track off), neutral-6 (dark track off),
// interactive-default (track on), neutral-12 (thumb), text-on-accent (thumb on)
//
// BEM structure rendered:
//   <label class="switch">
//     <!-- base-ui Root renders a <span class="switch__track"> with hidden <input> sibling -->
//     <span class="switch__track">
//       <span class="switch__thumb" />
//     </span>
//     <span class="switch__label">…</span>   ← optional, from label prop
//   </label>

interface SwitchProps extends SwitchPrimitive.Root.Props {
  /** Optional visible label text rendered as .switch__label */
  label?: React.ReactNode
  /** Additional className applied to the outer .switch wrapper */
  wrapperClassName?: string
}

function Switch({ className, label, wrapperClassName, ...props }: SwitchProps) {
  return (
    <label
      data-slot="switch-wrapper"
      className={cn("switch", wrapperClassName)}
    >
      <SwitchPrimitive.Root
        data-slot="switch"
        className={cn("switch__track", className)}
        {...props}
      >
        <SwitchPrimitive.Thumb
          data-slot="switch-thumb"
          className="switch__thumb"
        />
      </SwitchPrimitive.Root>
      {label && (
        <span data-slot="switch-label" className="switch__label">
          {label}
        </span>
      )}
    </label>
  )
}

export { Switch }
