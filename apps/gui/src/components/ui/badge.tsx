import { cva, type VariantProps } from "class-variance-authority"
import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"

import { cn } from "@/utils/helpers"

// Base: .badge — inline-flex, mono font, 2xs text, medium weight, wide tracking,
// uppercase, tight leading, full radius, thin transparent border, no-wrap
const badgeVariants = cva(
  [
    "inline-flex items-center gap-1",
    "px-2 py-0.5",
    "font-mono text-2xs font-medium tracking-wide uppercase leading-tight",
    "rounded-full border border-transparent",
    "whitespace-nowrap",
  ],
  {
    variants: {
      variant: {
        // .badge--accent
        accent:   "bg-accent-3 text-accent-11",
        // .badge--success
        success:  "bg-success-3 text-success-11",
        // .badge--warning
        warning:  "bg-warning-3 text-warning-11",
        // .badge--danger
        danger:   "bg-danger-3 text-danger-11",
        // .badge--info
        info:     "bg-info-3 text-info-11",
        // .badge--neutral
        neutral:  "bg-neutral-3 text-neutral-10",
        // .badge--outline
        outline:  "bg-transparent border-border-default text-secondary",
      },
    },
    defaultVariants: {
      variant: "accent",
    },
  }
)

type BadgeVariant = NonNullable<VariantProps<typeof badgeVariants>["variant"]>

interface BadgeProps extends useRender.ComponentProps<"span"> {
  variant?: BadgeVariant
}

// BadgeDot: dot indicator — .badge__dot: 6px circle, currentColor fill, flex-shrink-0
function BadgeDot({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "size-1.5 rounded-full bg-current flex-shrink-0",
        className
      )}
      data-slot="badge-dot"
    />
  )
}

function Badge({
  className,
  variant = "accent",
  render,
  ...props
}: BadgeProps) {
  return useRender({
    defaultTagName: "span",
    props: mergeProps<"span">(
      {
        className: cn(badgeVariants({ variant }), className),
      },
      props
    ),
    render,
    state: {
      slot: "badge",
      variant,
    },
  })
}

export { Badge, BadgeDot, badgeVariants }
