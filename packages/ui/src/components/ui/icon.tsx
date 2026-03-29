import { cva, type VariantProps } from "class-variance-authority"
import * as React from "react"

import { cn } from "../../utils/helpers"

// .icon: inline-flex, items-center, justify-center, flex-shrink-0, currentColor
// .icon svg: width/height 100%, stroke currentColor, fill none, stroke-width 1.5,
//            stroke-linecap round, stroke-linejoin round
//
// Icon sizes (from --icon-size-* tokens):
//   xs = 12px → size-3
//   sm = 14px → size-3.5
//   md = 16px → size-4
//   lg = 20px → size-5
//   xl = 24px → size-6

const iconVariants = cva(
  "inline-flex items-center justify-center flex-shrink-0 text-current [&_svg]:size-full [&_svg]:stroke-current [&_svg]:fill-none [&_svg]:stroke-[1.5] [&_svg]:[stroke-linecap:round] [&_svg]:[stroke-linejoin:round]",
  {
    variants: {
      size: {
        xs: "size-3",
        sm: "size-3.5",
        md: "size-4",
        lg: "size-5",
        xl: "size-6",
      },
    },
    defaultVariants: {
      size: "md",
    },
  }
)

type IconSize = NonNullable<VariantProps<typeof iconVariants>["size"]>

interface IconProps extends React.HTMLAttributes<HTMLSpanElement> {
  size?: IconSize
  /** Decorative icons should be aria-hidden on the parent or pass aria-hidden */
  "aria-hidden"?: boolean | "true" | "false"
}

function Icon({
  className,
  size = "md",
  children,
  ...props
}: IconProps) {
  return (
    <span
      data-slot="icon"
      className={cn(iconVariants({ size }), className)}
      {...props}
    >
      {children}
    </span>
  )
}

export { Icon, iconVariants }
export type { IconSize, IconProps }
