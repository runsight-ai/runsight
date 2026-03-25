import * as React from "react"
import { ChevronRight } from "lucide-react"

import { cn } from "@/utils/helpers"

// ---------------------------------------------------------------------------
// Breadcrumb root
// ---------------------------------------------------------------------------

export interface BreadcrumbProps extends React.ComponentPropsWithoutRef<"nav"> {
  separator?: React.ReactNode
}

export function Breadcrumb({
  separator,
  className,
  ...props
}: BreadcrumbProps) {
  return (
    <nav
      aria-label="breadcrumb"
      className={cn("flex", className)}
      {...props}
    />
  )
}

// ---------------------------------------------------------------------------
// BreadcrumbList
// ---------------------------------------------------------------------------

export function BreadcrumbList({
  className,
  ...props
}: React.ComponentPropsWithoutRef<"ol">) {
  return (
    <ol
      className={cn(
        "flex flex-wrap items-center gap-1 text-sm font-size-sm",
        className,
      )}
      {...props}
    />
  )
}

// ---------------------------------------------------------------------------
// BreadcrumbItem
// ---------------------------------------------------------------------------

export function BreadcrumbItem({
  className,
  ...props
}: React.ComponentPropsWithoutRef<"li">) {
  return (
    <li
      className={cn("inline-flex items-center gap-1", className)}
      {...props}
    />
  )
}

// ---------------------------------------------------------------------------
// BreadcrumbLink — ancestor items (clickable, secondary text)
// ---------------------------------------------------------------------------

export interface BreadcrumbLinkProps
  extends React.ComponentPropsWithoutRef<"a"> {
  asChild?: boolean
}

export function BreadcrumbLink({
  className,
  ...props
}: BreadcrumbLinkProps) {
  return (
    <a
      className={cn(
        "text-sm text-text-secondary transition-colors hover:text-text-primary",
        className,
      )}
      {...props}
    />
  )
}

// ---------------------------------------------------------------------------
// BreadcrumbPage — current (active) item
// ---------------------------------------------------------------------------

export function BreadcrumbPage({
  className,
  ...props
}: React.ComponentPropsWithoutRef<"span">) {
  return (
    <span
      role="link"
      aria-current="page"
      aria-disabled="true"
      className={cn("text-sm font-medium text-text-heading", className)}
      {...props}
    />
  )
}

// ---------------------------------------------------------------------------
// BreadcrumbSeparator — muted separator between items
// ---------------------------------------------------------------------------

export function BreadcrumbSeparator({
  children,
  className,
  ...props
}: React.ComponentPropsWithoutRef<"li">) {
  return (
    <li
      role="presentation"
      aria-hidden="true"
      className={cn("text-text-muted [&>svg]:size-3", className)}
      {...props}
    >
      {children ?? <ChevronRight />}
    </li>
  )
}

// ---------------------------------------------------------------------------
// BreadcrumbEllipsis — truncation indicator
// ---------------------------------------------------------------------------

export function BreadcrumbEllipsis({
  className,
  ...props
}: React.ComponentPropsWithoutRef<"span">) {
  return (
    <span
      role="presentation"
      aria-hidden="true"
      className={cn(
        "flex size-5 items-center justify-center text-text-muted",
        className,
      )}
      {...props}
    >
      <span className="text-text-secondary">…</span>
    </span>
  )
}
