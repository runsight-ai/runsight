import { Switch as SwitchPrimitive } from "@base-ui/react/switch"

import { cn } from "@/utils/helpers"

// Design tokens: neutral-5 (track off), neutral-6 (dark track off),
// interactive-default (track on), neutral-12 (thumb), text-on-accent (thumb on)
function Switch({
  className,
  ...props
}: SwitchPrimitive.Root.Props) {
  return (
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
  )
}

export { Switch }
