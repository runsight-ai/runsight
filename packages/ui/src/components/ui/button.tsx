import { cva, type VariantProps } from "class-variance-authority"
import { Button as ButtonPrimitive } from "@base-ui/react/button"

import { cn } from "../../utils/helpers"

const buttonVariants = cva(
  // Base styles — translated from .btn
  [
    "inline-flex items-center justify-center gap-1.5",
    "font-medium text-sm leading-tight tracking-slight",
    "border border-transparent rounded-md",
    "cursor-pointer select-none whitespace-nowrap",
    "transition-colors duration-100 ease-default",
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-focus",
    "disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none",
    "aria-disabled:opacity-50 aria-disabled:cursor-not-allowed aria-disabled:pointer-events-none",
  ],
  {
    variants: {
      variant: {
        // .btn--primary
        primary: [
          "bg-interactive-default text-on-accent border-interactive-default",
          "hover:bg-interactive-hover hover:border-interactive-hover",
          "active:bg-interactive-active active:border-interactive-active",
        ],
        // .btn--secondary
        secondary: [
          "bg-surface-tertiary text-primary border-border-default",
          "hover:bg-surface-hover hover:border-border-hover hover:text-heading",
          "active:bg-surface-active",
        ],
        // .btn--ghost
        ghost: [
          "bg-transparent text-secondary border-transparent",
          "hover:bg-surface-hover hover:text-primary",
          "active:bg-surface-active",
        ],
        // .btn--danger
        danger: [
          "bg-danger-9 text-on-accent border-danger-9",
          "hover:bg-danger-10 hover:border-danger-10",
          "active:bg-danger-8",
        ],
        // .btn--icon + .btn--ghost (icon-only square button)
        "icon-only": [
          "bg-transparent text-secondary border-transparent p-0 aspect-square",
          "hover:bg-surface-hover hover:text-primary",
          "active:bg-surface-active",
        ],
      },
      size: {
        // .btn--xs: height 24px, px-2, text-2xs, gap-1, radius-sm
        // leading-tight repeated per size to survive tailwind-merge (tw-merge v3
        // treats text-* as setting line-height, stripping leading-* from base)
        xs: "h-6 px-2 text-2xs leading-tight gap-1 rounded-sm",
        // compact icon button used across shared headers and overlays
        "icon-sm": "h-8 w-8 p-0",
        // .btn--sm: height 32px, px-3, text-sm
        sm: "h-8 px-3 text-sm leading-tight",
        // .btn--md: height 40px, px-4, text-md
        md: "h-10 px-4 text-md leading-tight",
        // .btn--lg: height 48px, px-6, text-md, gap-2
        lg: "h-12 px-6 text-md leading-tight gap-2",
      },
    },
    compoundVariants: [
      // icon-only should match the height of the selected size (square)
      { variant: "icon-only", size: "xs", className: "h-6 w-6" },
      { variant: "icon-only", size: "icon-sm", className: "h-8 w-8" },
      { variant: "icon-only", size: "sm", className: "h-8 w-8" },
      { variant: "icon-only", size: "md", className: "h-10 w-10" },
      { variant: "icon-only", size: "lg", className: "h-12 w-12" },
    ],
    defaultVariants: {
      variant: "primary",
      size: "sm",
    },
  }
)

type ButtonVariantProps = VariantProps<typeof buttonVariants>

interface ButtonProps extends ButtonPrimitive.Props {
  variant?: ButtonVariantProps["variant"]
  size?: ButtonVariantProps["size"]
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
          className="absolute inline-block size-3.5 rounded-full border-2 border-current border-r-transparent animate-spin text-on-accent"
        />
      )}
    </ButtonPrimitive>
  )
}

export { Button, buttonVariants }
