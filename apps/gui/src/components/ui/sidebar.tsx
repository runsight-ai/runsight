import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/utils/helpers"

// Design system tokens:
// sidebar-width-expanded, sidebar-width-collapsed
// sidebar-bg, sidebar-border, sidebar-fg, sidebar-hover, sidebar-muted
// sidebar-active-indicator (amber left bar)
// surface-selected, text-heading, text-muted, text-accent
// icon-size-md, control-height-sm (nav item height), font-size-md
// font-mono, font-size-2xs, tracking-wider, radius-md

// ---------------------------------------------------------------------------
// CVA variants
// ---------------------------------------------------------------------------

const sidebarItemVariants = cva(
  [
    // base layout
    "flex items-center gap-2",
    "h-[var(--density-nav-item-height,var(--control-height-sm))]",
    "px-2 rounded-[var(--radius-md)]",
    // typography
    "text-[length:var(--font-size-md)] text-(--sidebar-fg)",
    "no-underline cursor-pointer whitespace-nowrap overflow-hidden",
    // transitions
    "transition-[background,color] duration-100",
    // focus
    "focus-visible:outline focus-visible:outline-[var(--focus-ring-width)] focus-visible:outline-[var(--focus-ring-color)] focus-visible:outline-offset-[-4px]",
    // position for ::before amber indicator
    "relative",
    // hover
    "hover:bg-(--sidebar-hover) hover:text-(--text-heading)",
  ].join(" "),
  {
    variants: {
      active: {
        true: [
          "bg-(--surface-selected) text-(--text-heading)",
          // amber left indicator bar via pseudo
          "before:content-[''] before:absolute before:left-0",
          "before:top-[var(--space-1-5)] before:bottom-[var(--space-1-5)]",
          "before:w-[var(--border-width-thick)]",
          "before:bg-(--sidebar-active-indicator)",
          "before:rounded-r-[var(--radius-xs)]",
        ].join(" "),
        false: "",
      },
    },
    defaultVariants: {
      active: false,
    },
  }
)

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SidebarNavItem {
  id: string
  label: string
  /** Icon node rendered in the icon slot */
  icon?: React.ReactNode
  /** Optional badge content (e.g. count) */
  badge?: React.ReactNode
  /** Section this item belongs to (matches SidebarSection.id) */
  section?: string
  /** Nested child items */
  children?: SidebarNavItem[]
}

export interface SidebarSection {
  id: string
  label?: string
}

interface SidebarProps extends React.HTMLAttributes<HTMLElement> {
  /** Whether the sidebar is in collapsed (icon-rail) mode */
  collapsed?: boolean
  /** Navigation items */
  items?: SidebarNavItem[]
  /** Sections — define ordering and optional labels */
  sections?: SidebarSection[]
  /** Active item id */
  activeId?: string
  /** Called when a nav item is clicked */
  onItemClick?: (id: string) => void
  /** Logo rendered at the top of the sidebar */
  logo?: React.ReactNode
  /** Header content rendered below the logo area */
  header?: React.ReactNode
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function Sidebar({
  className,
  collapsed = false,
  items = [],
  sections = [],
  activeId,
  onItemClick,
  logo,
  header,
  children,
  ...props
}: SidebarProps) {
  const hasSections = sections.length > 0

  function renderItem(item: SidebarNavItem) {
    const isActive = item.id === activeId
    const iconColorClass = isActive ? "text-(--text-accent)" : "text-(--text-muted)"

    return (
      <div
        key={item.id}
        className={cn(sidebarItemVariants({ active: isActive }))}
        role="menuitem"
        tabIndex={0}
        aria-current={isActive ? "page" : undefined}
        onClick={() => onItemClick?.(item.id)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault()
            onItemClick?.(item.id)
          }
        }}
      >
        {item.icon && (
          <span
            className={cn(
              "flex-shrink-0 w-(--icon-size-md) h-(--icon-size-md)",
              iconColorClass,
              // In collapsed mode the icon is the only visible element
              collapsed ? "mx-auto" : ""
            )}
          >
            {item.icon}
          </span>
        )}

        {/* Hidden in collapsed mode */}
        <span className={cn("overflow-hidden text-ellipsis", collapsed && "hidden")}>
          {item.label}
        </span>

        {item.badge !== undefined && (
          <span className={cn("ml-auto flex-shrink-0", collapsed && "hidden")}>
            {item.badge}
          </span>
        )}
      </div>
    )
  }

  function renderNestedItems(childItems: SidebarNavItem[]) {
    return (
      <div className="pl-6">
        {childItems.map(renderItem)}
      </div>
    )
  }

  return (
    <nav
      data-slot="sidebar"
      className={cn(
        // base
        "flex flex-col overflow-y-auto overflow-x-hidden flex-shrink-0 h-full",
        "bg-(--sidebar-bg) border-r border-(--sidebar-border)",
        // width transition
        "transition-[width] duration-200 ease-out",
        collapsed
          ? "w-(--sidebar-width-collapsed)"
          : "w-(--sidebar-width-expanded)",
        className
      )}
      aria-label="Navigation"
      {...props}
    >
      {/* Logo / branding area */}
      {logo && (
        <div className="px-2 py-2">{logo}</div>
      )}

      {/* Optional header slot */}
      {header && (
        <div className="px-2 py-2">{header}</div>
      )}

      {hasSections ? (
        sections.map((section) => {
          const sectionItems = items.filter((i) => i.section === section.id)
          return (
            <div key={section.id} className="px-2 py-2">
              {section.label && (
                <div
                  className={cn(
                    "font-mono text-[length:var(--font-size-2xs)] font-medium",
                    "tracking-[var(--tracking-wider)] uppercase text-(--sidebar-muted)",
                    "px-2 py-2",
                    // Hidden in collapsed mode
                    collapsed && "hidden"
                  )}
                >
                  {section.label}
                </div>
              )}
              {sectionItems.map((item) => (
                <React.Fragment key={item.id}>
                  {renderItem(item)}
                  {item.children && item.children.length > 0 &&
                    renderNestedItems(item.children)}
                </React.Fragment>
              ))}
            </div>
          )
        })
      ) : (
        <div className="px-2 py-2">
          {items.map((item) => (
            <React.Fragment key={item.id}>
              {renderItem(item)}
              {item.children && item.children.length > 0 &&
                renderNestedItems(item.children)}
            </React.Fragment>
          ))}
        </div>
      )}

      {/* Render arbitrary children (e.g. footer section) */}
      {children}
    </nav>
  )
}

export { Sidebar }
export type { SidebarProps }
