import * as React from "react"

import { cn } from "@/utils/helpers"

// Design system tokens:
// .link: text-accent, no underline, transition color duration-100
// .link:hover: interactive-hover, underline, underline-offset 2px
// .link--muted: text-secondary; hover → text-primary
// .link--external::after: content ' ↗', font-size 0.8em (appended via CSS)

const linkVariants = {
  default: "",
  muted: "link--muted",
  external: "link--external",
} as const

type LinkVariant = keyof typeof linkVariants

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
      className={cn(
        "link",
        linkVariants[variant],
        className
      )}
      {...props}
    >
      {children}
    </a>
  )
}

export { Link }
export type { LinkVariant, LinkProps }
