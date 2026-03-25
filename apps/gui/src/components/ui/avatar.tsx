import * as React from "react"

import { cn } from "@/utils/helpers"

// Design system tokens:
// Default: control-height-sm, accent-3/accent-11, font-size-xs, font-weight-semibold, radius-full
// .avatar--sm: control-height-xs, font-size-2xs
// .avatar--lg: control-height-md, font-size-md
// .avatar-group: row-reverse flex, negative left margin (space-neg-2) except last child

const sizeVariants = {
  sm: "avatar--sm",
  default: "",
  lg: "avatar--lg",
} as const

type AvatarSize = keyof typeof sizeVariants

interface AvatarProps extends React.HTMLAttributes<HTMLDivElement> {
  size?: AvatarSize
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
      className={cn(
        "avatar",
        sizeVariants[size],
        className
      )}
      {...props}
    >
      {src ? (
        <img src={src} alt={alt} />
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
      className={cn("avatar-group", className)}
      {...props}
    >
      {children}
    </div>
  )
}

export { Avatar, AvatarGroup }
export type { AvatarSize, AvatarProps, AvatarGroupProps }
