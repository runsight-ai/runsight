import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"

import { cn } from "@/utils/helpers"

// Design system tokens: font-mono, font-size-2xs, tracking-wide, radius-full
// Semantic color scales: accent-3/accent-11, success-3/success-11, warning-3/warning-11,
//   danger-3/danger-11, info-3/info-11, neutral-3/neutral-10
// text-on-accent used for badge base; badge BEM classes apply all token values

// Variant → BEM modifier map (exported for tests and external consumers)
export const badgeVariants = {
  variant: {
    accent: "badge--accent",
    success: "badge--success",
    warning: "badge--warning",
    danger: "badge--danger",
    info: "badge--info",
    neutral: "badge--neutral",
    outline: "badge--outline",
  },
} as const

type BadgeVariant = keyof typeof badgeVariants.variant

interface BadgeProps extends useRender.ComponentProps<"span"> {
  variant?: BadgeVariant
}

// BadgeDot: dot indicator using currentColor (badge__dot pattern)
function BadgeDot({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn("badge__dot", className)}
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
        className: cn(
          "badge",
          badgeVariants.variant[variant],
          className
        ),
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

export { Badge, BadgeDot }
