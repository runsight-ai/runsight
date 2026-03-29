import { cva, type VariantProps } from "class-variance-authority"
import * as React from "react"

import { cn } from "../../utils/helpers"

// .link: text-accent, no underline, cursor pointer, transition color 100ms
// .link:hover: interactive-hover, underline, underline-offset 2px
// .link--muted: text-secondary; hover → text-primary
// .link--external::after: content ' ↗' rendered via JSX (avoids CSS pseudo-element dependency)

const linkVariants = cva(
  [
    "cursor-pointer no-underline",
    "transition-colors duration-100 ease-default",
    "hover:underline hover:underline-offset-2",
  ],
  {
    variants: {
      variant: {
        // .link (default): text-accent, hover → interactive-hover
        default:  "text-accent hover:text-interactive-hover",
        // .link--muted: text-secondary, hover → text-primary
        muted:    "text-secondary hover:text-primary",
        // .link--external: same as default, appends ↗ arrow via JSX
        external: "text-accent hover:text-interactive-hover",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

type LinkVariant = NonNullable<VariantProps<typeof linkVariants>["variant"]>

interface LinkProps extends React.AnchorHTMLAttributes<HTMLAnchorElement> {
  variant?: LinkVariant
}

function Link({
  className,
  variant = "default",
  children,
  ...props
}: LinkProps) {
  return (
    <a
      data-slot="link"
      className={cn(linkVariants({ variant }), className)}
      {...props}
    >
      {children}
      {variant === "external" && (
        <span aria-hidden="true" className="text-[0.8em]"> ↗</span>
      )}
    </a>
  )
}

export { Link, linkVariants }
export type { LinkVariant, LinkProps }
