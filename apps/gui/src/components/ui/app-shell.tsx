// Design system tokens:
// header-height, status-bar-height,
// sidebar-width-collapsed, sidebar-width-expanded,
// inspector-width, z-overlay, elevation-overlay-shadow,
// surface-primary, surface-secondary, border-subtle

import * as React from "react"

import { cn } from "@/utils/helpers"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AppShellProps {
  /** Whether the sidebar is in its collapsed (icon-only) state */
  sidebarCollapsed?: boolean
  /** Whether the inspector panel is visible */
  inspectorOpen?: boolean
  /** Slot for the top header bar */
  header?: React.ReactNode
  /** Slot for the left sidebar */
  sidebar?: React.ReactNode
  /** Slot for the main canvas / content area */
  main?: React.ReactNode
  /** Slot for the right inspector panel */
  inspector?: React.ReactNode
  /** Slot for the bottom status bar */
  statusBar?: React.ReactNode
  /** Additional class names applied to the outermost grid container */
  className?: string
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * AppShell — full-viewport CSS Grid layout shell.
 *
 * Grid areas (row × column):
 *   ┌────────────────────────────────────────────┐
 *   │          header (full width)               │  header-height
 *   ├──────────┬─────────────────────┬───────────┤
 *   │          │                     │           │
 *   │ sidebar  │       main          │ inspector │  1fr
 *   │          │                     │           │
 *   ├──────────┴─────────────────────┴───────────┤
 *   │          status-bar (full width)           │  status-bar-height
 *   └────────────────────────────────────────────┘
 *
 * Uses data-sidebar and data-inspector attributes to drive column widths
 * via CSS custom properties (same approach as the original BEM .app-shell).
 */
export function AppShell({
  sidebarCollapsed = false,
  inspectorOpen = true,
  header,
  sidebar,
  main,
  inspector,
  statusBar,
  className,
}: AppShellProps) {
  return (
    <div
      data-slot="app-shell"
      data-sidebar={sidebarCollapsed ? "collapsed" : "expanded"}
      data-inspector={inspectorOpen ? "open" : "closed"}
      className={cn(
        // Grid structure mirroring .app-shell spec
        "grid h-screen w-screen overflow-hidden",
        "bg-(--surface-primary) text-(--text-primary)",
        // Grid rows: header / content / status-bar
        "[grid-template-rows:var(--header-height)_1fr_var(--status-bar-height)]",
        // Grid columns: sidebar / main / inspector
        // Inspector column collapses to 0 when closed
        "[grid-template-columns:auto_1fr_auto]",
        // Named grid areas
        "[grid-template-areas:'header_header_header'_'sidebar_main_inspector'_'status_status_status']",
        // Inspector closed → collapse last column
        "data-[inspector=closed]:[grid-template-columns:auto_1fr_0]",
        // Sidebar expanded/collapsed widths applied to the aside via data attr
        className
      )}
    >
      {/* ---------------------------------------------------------------- */}
      {/* Header — spans all columns                                        */}
      {/* ---------------------------------------------------------------- */}
      <header
        data-slot="app-shell-header"
        className={cn(
          "[grid-area:header]",
          "border-b border-(--border-subtle) bg-(--surface-secondary)"
        )}
      >
        {header}
      </header>

      {/* ---------------------------------------------------------------- */}
      {/* Sidebar                                                           */}
      {/* Width driven by data-sidebar on parent via CSS var               */}
      {/* ---------------------------------------------------------------- */}
      <aside
        data-slot="app-shell-sidebar"
        className={cn(
          "[grid-area:sidebar]",
          "border-r border-(--border-subtle) bg-(--surface-secondary)",
          "overflow-y-auto",
          // Width transitions between expanded/collapsed via CSS var
          "transition-[width] duration-200 ease-out",
          // When parent is collapsed, width shrinks
          "[[data-sidebar=expanded]_&]:w-(--sidebar-width-expanded)",
          "[[data-sidebar=collapsed]_&]:w-(--sidebar-width-collapsed)",
          // Mobile: fixed drawer, hidden by default
          "max-md:fixed max-md:left-0 max-md:top-[var(--header-height)] max-md:bottom-0",
          "max-md:z-[var(--z-overlay)] max-md:-translate-x-full",
          "max-md:transition-transform max-md:duration-200 max-md:ease-out",
          "max-md:[[data-sidebar=open]_&]:translate-x-0"
        )}
      >
        {sidebar}
      </aside>

      {/* ---------------------------------------------------------------- */}
      {/* Main content / canvas                                             */}
      {/* ---------------------------------------------------------------- */}
      <main
        data-slot="app-shell-main"
        className={cn(
          "[grid-area:main]",
          "overflow-auto relative",
          "bg-(--surface-primary)"
        )}
      >
        {main}
      </main>

      {/* ---------------------------------------------------------------- */}
      {/* Inspector panel                                                   */}
      {/* ---------------------------------------------------------------- */}
      <aside
        data-slot="app-shell-inspector"
        className={cn(
          "[grid-area:inspector]",
          "border-l border-(--border-subtle) bg-(--surface-secondary)",
          "overflow-y-auto",
          // Hidden when parent data-inspector=closed (column collapses to 0)
          "[[data-inspector=closed]_&]:hidden",
          // Tablet: fixed overlay drawer on the right
          "max-lg:fixed max-lg:right-0 max-lg:top-[var(--header-height)] max-lg:bottom-0",
          "max-lg:w-(--inspector-width) max-lg:max-w-[80vw]",
          "max-lg:z-[var(--z-overlay)]",
          "max-lg:shadow-[var(--elevation-overlay-shadow)]",
          "max-lg:translate-x-full max-lg:transition-transform max-lg:duration-200 max-lg:ease-out",
          "max-lg:[[data-inspector=open]_&]:translate-x-0"
        )}
      >
        {inspector}
      </aside>

      {/* ---------------------------------------------------------------- */}
      {/* Status bar — spans all columns                                    */}
      {/* ---------------------------------------------------------------- */}
      <footer
        data-slot="app-shell-status-bar"
        className={cn(
          "[grid-area:status]",
          "border-t border-(--border-subtle) bg-(--surface-secondary)"
        )}
      >
        {statusBar}
      </footer>
    </div>
  )
}
