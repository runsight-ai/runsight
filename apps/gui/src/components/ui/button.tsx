import { Button as ButtonPrimitive } from "@base-ui/react/button"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/utils/helpers"

// Design system tokens: font-size-md, font-weight-medium, radius-md, control-height-*
const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center rounded-radius-md border border-transparent bg-clip-padding whitespace-nowrap transition-all outline-none select-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-border-focus/50 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        primary:
          "bg-interactive text-on-accent border-interactive hover:bg-interactive-hover hover:border-interactive-hover active:bg-interactive-active",
        secondary:
          "bg-surface-tertiary text-primary border-border-default hover:bg-surface-hover hover:border-border-hover active:bg-surface-active",
        ghost:
          "bg-transparent text-secondary border-transparent hover:bg-surface-hover hover:text-primary active:bg-surface-active",
        danger:
          "bg-danger-9 text-on-accent border-danger-9 hover:bg-danger-10 hover:border-danger-10 active:bg-danger-8",
        "icon-only":
          "bg-transparent text-secondary border-transparent hover:bg-surface-hover hover:text-primary active:bg-surface-active aspect-square p-0",
      },
      size: {
        xs: "h-control-height-xs px-2 text-font-size-2xs gap-1 rounded-radius-sm",
        sm: "h-control-height-sm px-3 text-font-size-sm gap-1.5",
        md: "h-control-height-md px-4 text-font-size-md gap-1.5 font-weight-medium",
        lg: "h-control-height-lg px-6 text-font-size-md gap-2 font-weight-medium",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "sm",
    },
  }
)

interface ButtonProps
  extends ButtonPrimitive.Props,
    VariantProps<typeof buttonVariants> {
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
        loading && "relative text-transparent pointer-events-none",
        className
      )}
      {...props}
    >
      {children}
      {loading && (
        <span
          aria-hidden="true"
          className="absolute inset-0 flex items-center justify-center"
        >
          <span className="size-4 animate-spin rounded-full border-2 border-current border-r-transparent" />
        </span>
      )}
    </ButtonPrimitive>
  )
}

export { Button, buttonVariants }
