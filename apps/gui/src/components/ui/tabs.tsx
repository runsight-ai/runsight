"use client"

import * as React from "react"
import { Tabs as TabsPrimitive } from "@base-ui/react/tabs"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/utils/helpers"

// ---------------------------------------------------------------------------
// Tabs root
// ---------------------------------------------------------------------------

function Tabs({
  className,
  orientation = "horizontal",
  ...props
}: TabsPrimitive.Root.Props) {
  return (
    <TabsPrimitive.Root
      data-slot="tabs"
      data-orientation={orientation}
      className={cn(className)}
      {...props}
    />
  )
}

// ---------------------------------------------------------------------------
// TabsList variants
// ---------------------------------------------------------------------------

const tabsListVariants = cva(
  // base — default horizontal underline tabs
  "flex border-b border-border-subtle gap-0",
  {
    variants: {
      variant: {
        default:   "",
        contained: [
          "border-b-0 bg-surface-tertiary rounded-md p-0.5 gap-0.5",
        ],
        vertical: [
          "flex-col border-b-0 border-r border-border-subtle gap-0.5",
        ],
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function TabsList({
  className,
  variant = "default",
  ...props
}: TabsPrimitive.List.Props & { variant?: "default" | "contained" | "vertical" }) {
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      className={cn(tabsListVariants({ variant }), className)}
      {...props}
    />
  )
}

// ---------------------------------------------------------------------------
// TabsTrigger
// The tab appearance changes based on the parent variant, which we express
// via data-attributes on the list. However, since TabsList is a separate
// component from TabsTrigger, we use CSS group/peer patterns or rely on the
// CSS cascade.  For pure Tailwind we encode all three contexts here using
// arbitrary group-data selectors so that the trigger responds to a
// [data-variant] on the parent list.
// ---------------------------------------------------------------------------

function TabsTrigger({ className, ...props }: TabsPrimitive.Tab.Props) {
  return (
    <TabsPrimitive.Tab
      data-slot="tabs-trigger"
      className={cn(
        // --- Default / underline tab ---
        "flex items-center gap-1.5 px-3 py-2",
        "font-body text-sm font-medium text-secondary",
        "bg-transparent border-0 border-b-2 border-b-transparent",
        "cursor-pointer whitespace-nowrap",
        "transition-[color,border-color] duration-100",
        // hover
        "hover:text-primary",
        // selected
        "aria-selected:text-heading aria-selected:border-b-interactive-default",
        // focus
        "focus-visible:outline-[length:var(--focus-ring-width)] focus-visible:outline-[var(--focus-ring-color)] focus-visible:-outline-offset-1",
        className
      )}
      {...props}
    />
  )
}

// ---------------------------------------------------------------------------
// TabsContent
// ---------------------------------------------------------------------------

function TabsContent({ className, ...props }: TabsPrimitive.Panel.Props) {
  return (
    <TabsPrimitive.Panel
      data-slot="tabs-content"
      className={cn("flex-1 outline-none", className)}
      {...props}
    />
  )
}

// ---------------------------------------------------------------------------
// TabBadge — mono, 2xs, muted, tertiary bg, pill
// ---------------------------------------------------------------------------

function TabBadge({ className, ...props }: React.ComponentPropsWithoutRef<"span">) {
  return (
    <span
      className={cn(
        "font-mono text-2xs text-muted bg-surface-tertiary",
        "px-1.5 rounded-full min-w-[var(--icon-size-md,16px)] text-center",
        className
      )}
      {...props}
    />
  )
}

export { Tabs, TabsList, TabsTrigger, TabsContent, TabBadge }
