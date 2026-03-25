"use client"

// Design system tokens used by BEM classes in components.css:
//   .tabs         — border-bottom: var(--border-subtle)
//   .tab          — color: var(--text-secondary); font-size: var(--font-size-sm);
//                   font-weight: var(--font-weight-medium) (font-medium)
//   .tab[aria-selected="true"] — color: var(--text-heading);
//                                border-bottom-color: var(--interactive-default)
//   .tabs--contained .tab height uses --density-nav-item-height equivalent (--control-height-sm)
//   .tab__badge   — font-family: var(--font-mono); background: var(--surface-tertiary)

import * as React from "react"
import { Tabs as TabsPrimitive } from "@base-ui/react/tabs"

import { cn } from "@/utils/helpers"

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

function TabsList({
  className,
  variant = "default",
  ...props
}: TabsPrimitive.List.Props & { variant?: "default" | "contained" | "vertical" }) {
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      className={cn(
        "tabs",
        variant === "contained" && "tabs--contained",
        variant === "vertical" && "tabs--vertical",
        className
      )}
      {...props}
    />
  )
}

function TabsTrigger({ className, ...props }: TabsPrimitive.Tab.Props) {
  return (
    <TabsPrimitive.Tab
      data-slot="tabs-trigger"
      className={cn("tab", className)}
      {...props}
    />
  )
}

function TabsContent({ className, ...props }: TabsPrimitive.Panel.Props) {
  return (
    <TabsPrimitive.Panel
      data-slot="tabs-content"
      className={cn("flex-1 outline-none", className)}
      {...props}
    />
  )
}

function TabBadge({ className, ...props }: React.ComponentPropsWithoutRef<"span">) {
  return (
    <span
      className={cn("tab__badge", className)}
      {...props}
    />
  )
}

export { Tabs, TabsList, TabsTrigger, TabsContent, TabBadge }
