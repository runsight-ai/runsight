import * as React from "react"
import { ChevronRight } from "lucide-react"
import { cva } from "class-variance-authority"

import { cn } from "../../utils/helpers"

// ---------------------------------------------------------------------------
// Breadcrumb context — carries separator down to BreadcrumbSeparator
// ---------------------------------------------------------------------------

const BreadcrumbContext = React.createContext<{ separator?: React.ReactNode }>({})

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
    <BreadcrumbContext.Provider value={{ separator }}>
      <nav
        aria-label="breadcrumb"
        className={cn(
          "flex items-center gap-1 text-sm overflow-hidden",
          className
        )}
        {...props}
      />
    </BreadcrumbContext.Provider>
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
// BreadcrumbLink variants
// ---------------------------------------------------------------------------

const breadcrumbItemVariants = cva(
  // base — muted, no underline, nowrap, transition to primary on hover
  "text-muted no-underline whitespace-nowrap transition-colors duration-100 hover:text-primary",
  {
    variants: {
      variant: {
        default: "",
        /** ID segments — monospace, xs */
        id: "font-mono text-xs",
      },
      current: {
        true: "text-heading font-medium",
        false: null,
      },
    },
    defaultVariants: {
      variant: "default",
      current: false,
    },
  }
)

export interface BreadcrumbLinkProps
  extends React.ComponentPropsWithoutRef<"a"> {
  asChild?: boolean
  /** variant="id" — monospace, xs font for IDs like "RUN-423" */
  variant?: "default" | "id"
}

export function BreadcrumbLink({
  className,
  variant = "default",
  ...props
}: BreadcrumbLinkProps) {
  return (
    <a
      className={cn(breadcrumbItemVariants({ variant, current: false }), className)}
      {...props}
    />
  )
}

// ---------------------------------------------------------------------------
// BreadcrumbPage — current (active) item
// ---------------------------------------------------------------------------

export interface BreadcrumbPageProps
  extends React.ComponentPropsWithoutRef<"span"> {
  /** variant="id" — monospace, xs font for IDs like "RUN-423" */
  variant?: "default" | "id"
}

export function BreadcrumbPage({
  className,
  variant = "default",
  ...props
}: BreadcrumbPageProps) {
  return (
    <span
      role="link"
      aria-current="page"
      aria-disabled="true"
      className={cn(breadcrumbItemVariants({ variant, current: true }), className)}
      {...props}
    />
  )
}

// ---------------------------------------------------------------------------
// BreadcrumbSeparator — text-muted, xs, flex-shrink-0
// ---------------------------------------------------------------------------

export function BreadcrumbSeparator({
  children,
  className,
  ...props
}: React.ComponentPropsWithoutRef<"li">) {
  const { separator } = React.useContext(BreadcrumbContext)
  return (
    <li
      role="presentation"
      aria-hidden="true"
      className={cn("text-muted text-xs flex-shrink-0", className)}
      {...props}
    >
      {children ?? separator ?? <ChevronRight />}
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
        "text-muted no-underline whitespace-nowrap transition-colors duration-100 hover:text-primary",
        className
      )}
      {...props}
    >
      <span>…</span>
    </span>
  )
}
