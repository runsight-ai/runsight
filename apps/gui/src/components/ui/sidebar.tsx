import * as React from "react"

import { cn } from "@/utils/helpers"

// Design system tokens:
// .sidebar: sidebar-width-expanded, sidebar-bg, sidebar-border, flex-col, overflow-y auto,
//           transition width duration-200
// .sidebar--collapsed: sidebar-width-collapsed; hides labels/badges/section-labels, centers items
// .sidebar__section: padding space-2
// .sidebar__section-label: font-mono, font-size-2xs, tracking-wider, uppercase, sidebar-muted
// .sidebar__item: flex, align-center, gap space-2, height density-nav-item-height,
//                 padding 0 space-2, radius-md, sidebar-fg, font-size-md, transition
// .sidebar__item:hover: sidebar-hover bg, text-heading
// .sidebar__item--active / [aria-current="page"]: surface-selected bg, text-heading,
//   ::before amber left bar (sidebar-active-indicator)
// .sidebar__item-icon: icon-size-md, text-muted; active → text-accent
// .sidebar__item-label: overflow hidden, text-overflow ellipsis
// .sidebar__item-badge: margin-left auto, flex-shrink 0
// .sidebar__nested: padding-left space-6

export interface SidebarNavItem {
  id: string
  label: string
  /** ReactNode rendered inside .sidebar__item-icon */
  icon?: React.ReactNode
  /** Optional badge content (e.g. count) rendered in .sidebar__item-badge */
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
  // If sections are provided, group items; otherwise render as a single flat section
  const hasSections = sections.length > 0

  function renderItem(item: SidebarNavItem) {
    const isActive = item.id === activeId
    return (
      <div
        key={item.id}
        className={cn(
          "sidebar__item",
          isActive && "sidebar__item--active"
        )}
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
          <span className="sidebar__item-icon">{item.icon}</span>
        )}
        <span className="sidebar__item-label">{item.label}</span>
        {item.badge !== undefined && (
          <span className="sidebar__item-badge">{item.badge}</span>
        )}
      </div>
    )
  }

  function renderNestedItems(children: SidebarNavItem[]) {
    return (
      <div className="sidebar__nested">
        {children.map(renderItem)}
      </div>
    )
  }

  return (
    <nav
      data-slot="sidebar"
      className={cn(
        "sidebar",
        collapsed && "sidebar--collapsed",
        className
      )}
      aria-label="Navigation"
      {...props}
    >
      {/* Logo / branding area */}
      {logo && (
        <div className="sidebar__section">{logo}</div>
      )}

      {/* Optional header slot */}
      {header && (
        <div className="sidebar__section">{header}</div>
      )}

      {hasSections ? (
        sections.map((section) => {
          const sectionItems = items.filter((i) => i.section === section.id)
          return (
            <div key={section.id} className="sidebar__section">
              {section.label && (
                <div className="sidebar__section-label">{section.label}</div>
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
        <div className="sidebar__section">
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
