import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/utils/helpers"

// Design system tokens: font-mono, font-size-2xs, tracking-wide, radius-full
// Semantic color scales: accent-3/accent-11, success-3/success-11, warning-3/warning-11,
//   danger-3/danger-11, info-3/info-11, neutral-3/neutral-10
const badgeVariants = cva(
  "group/badge inline-flex h-5 w-fit shrink-0 items-center justify-center gap-1 overflow-hidden rounded-radius-full border border-transparent px-2 py-0.5 font-mono text-font-size-2xs font-weight-medium tracking-wide uppercase whitespace-nowrap",
  {
    variants: {
      variant: {
        accent: "bg-accent-3 text-accent-11",
        success: "bg-success-3 text-success-11",
        warning: "bg-warning-3 text-warning-11",
        danger: "bg-danger-3 text-danger-11",
        info: "bg-info-3 text-info-11",
        neutral: "bg-neutral-3 text-neutral-10",
        outline: "border-border-default bg-transparent text-secondary",
      },
    },
    defaultVariants: {
      variant: "accent",
    },
  }
)

// BadgeDot: 6px circle dot indicator using currentColor (badge__dot pattern)
function BadgeDot({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-block size-1.5 rounded-full bg-current flex-shrink-0",
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
}: useRender.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
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
