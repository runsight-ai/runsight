import { Button as ButtonPrimitive } from "@base-ui/react/button"

import { cn } from "@/utils/helpers"

// Design system BEM classes — tokens referenced:
// interactive-default, text-on-accent, surface-tertiary, text-secondary
// danger-9, radius-md, font-size-md, font-weight-medium, control-height-*

// Variant → BEM modifier map. Keys are the public variant names.
const bemVariants = {
  variant: {
    primary:     "btn--primary",
    secondary:   "btn--secondary",
    ghost:       "btn--ghost",
    danger:      "btn--danger",
    "icon-only": "btn--icon btn--ghost",
  },
  size: {
    xs: "btn--xs",
    sm: "btn--sm",
    md: "btn--md",
    lg: "btn--lg",
  },
  defaultVariants: {
    variant: "primary",
    size:    "sm",
  },
} as const

type ButtonVariant = keyof typeof bemVariants.variant
type ButtonSize    = keyof typeof bemVariants.size

function buttonVariants({
  variant = "primary",
  size = "sm",
}: {
  variant?: ButtonVariant
  size?: ButtonSize
} = {}) {
  return cn("btn", bemVariants.variant[variant], bemVariants.size[size])
}

interface ButtonProps extends ButtonPrimitive.Props {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
}

function Button({
  className,
  variant = "primary",
  size = "sm",
  loading = false,
  disabled,
  children,
  ...props
}: ButtonProps) {
  return (
    <ButtonPrimitive
      data-slot="button"
      aria-busy={loading ? true : undefined}
      disabled={disabled || loading}
      className={cn(
        buttonVariants({ variant, size }),
        loading && "btn--loading",
        className
      )}
      {...props}
    >
      {children}
    </ButtonPrimitive>
  )
}

export { Button, buttonVariants }
