import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "../../utils/helpers"

// Design system tokens:
// Default: control-height-sm=32px (w-8 h-8), accent-3 bg, accent-11 text,
//          font-size-xs=12px, font-weight-semibold (600), radius-full, flex-shrink-0
// .avatar--sm: control-height-xs=24px (w-6 h-6), font-size-2xs=11px
// .avatar--lg: control-height-md=40px (w-10 h-10), font-size-md=14px
// .avatar img: w-full h-full object-cover
// .avatar-group: flex-row-reverse, each avatar gets -ml-2 (space-neg-2=-8px)
//   except last child (ml-0), border-width-thick (2px) solid surface-primary

const avatarVariants = cva(
  [
    "inline-flex items-center justify-center",
    "rounded-full overflow-hidden shrink-0",
    "bg-accent-3 text-accent-11",
    "font-body font-semibold",
  ].join(" "),
  {
    variants: {
      size: {
        // control-height-xs = 24px, font-size-2xs = 11px
        sm:      "w-6 h-6 text-2xs",
        // control-height-sm = 32px, font-size-xs = 12px
        default: "w-8 h-8 text-xs",
        // control-height-md = 40px, font-size-md = 14px
        lg:      "w-10 h-10 text-md",
      },
    },
    defaultVariants: {
      size: "default",
    },
  }
)

type AvatarSize = "sm" | "default" | "lg"

interface AvatarProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof avatarVariants> {
  /** Image URL. When provided, renders an <img> inside the avatar. */
  src?: string
  /** Alt text for the image */
  alt?: string
}

function Avatar({
  className,
  size = "default",
  src,
  alt = "",
  children,
  ...props
}: AvatarProps) {
  return (
    <div
      data-slot="avatar"
      className={cn(avatarVariants({ size }), className)}
      {...props}
    >
      {src ? (
        <img src={src} alt={alt} className="w-full h-full object-cover" />
      ) : (
        children
      )}
    </div>
  )
}

interface AvatarGroupProps extends React.HTMLAttributes<HTMLDivElement> {}

function AvatarGroup({ className, children, ...props }: AvatarGroupProps) {
  return (
    <div
      data-slot="avatar-group"
      className={cn(
        // flex-direction: row-reverse
        "flex flex-row-reverse",
        className
      )}
      {...props}
    >
      {/* Each avatar inside a group gets -ml-2 + border except the last (first in DOM due to row-reverse) */}
      {React.Children.map(children, (child, index) => {
        if (!React.isValidElement(child)) return child
        const isFirst = index === 0
        return React.cloneElement(child as React.ReactElement<{ className?: string }>, {
          className: cn(
            (child as React.ReactElement<{ className?: string }>).props.className,
            // last-child in visual order = first in DOM (row-reverse), so index 0 gets ml-0
            isFirst
              ? "ml-0 border-2 border-surface-primary"
              : "-ml-2 border-2 border-surface-primary"
          ),
        })
      })}
    </div>
  )
}

export { Avatar, AvatarGroup }
export type { AvatarSize, AvatarProps, AvatarGroupProps }
