import * as React from "react"
import { ChevronRight } from "lucide-react"

// Design system tokens used by BEM classes in components.css:
//   .breadcrumb          — font-size: var(--font-size-sm); gap: var(--space-1)
//   .breadcrumb__item    — color: var(--text-muted); transition to var(--text-primary) on hover
//   .breadcrumb__item:hover — color: var(--text-primary)
//   .breadcrumb__item[aria-current="page"] — color: var(--text-heading);
//                                            font-weight: var(--font-weight-medium)
//   .breadcrumb__separator — color: var(--text-muted); font-size: var(--font-size-xs)
//   .breadcrumb__item--id  — font-family: var(--font-mono); font-size: var(--font-size-xs)
// Ancestor items use text-secondary for body text before hover state transitions to text-primary.

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
      className={cn("breadcrumb", className)}
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
      className={cn("flex flex-wrap items-center", className)}
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
      className={cn("inline-flex items-center", className)}
      {...props}
    />
  )
}

// ---------------------------------------------------------------------------
// BreadcrumbLink — ancestor items (clickable, text-secondary → text-primary on hover)
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
      className={cn("breadcrumb__item", className)}
      {...props}
    />
  )
}

// ---------------------------------------------------------------------------
// BreadcrumbPage — current (active) item; aria-current triggers text-heading color
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
      className={cn("breadcrumb__item", className)}
      {...props}
    />
  )
}

// ---------------------------------------------------------------------------
// BreadcrumbSeparator — uses breadcrumb__separator (text-muted, font-size-xs)
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
      className={cn("breadcrumb__separator", className)}
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
      className={cn("breadcrumb__item", className)}
      {...props}
    >
      <span>…</span>
    </span>
  )
}
