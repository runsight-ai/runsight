// Design system tokens: header-height, status-bar-height,
// sidebar-width-collapsed, sidebar-width-expanded,
// inspector-width, inspector-width-min, inspector-width-max,
// surface-primary, border-subtle

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
      className={cn("app-shell", className)}
    >
      {/* ---------------------------------------------------------------- */}
      {/* Header — spans all columns                                        */}
      {/* ---------------------------------------------------------------- */}
      <header
        data-slot="app-shell-header"
        className="app-shell__header border-b border-border-subtle bg-surface-secondary"
      >
        {header}
      </header>

      {/* ---------------------------------------------------------------- */}
      {/* Sidebar                                                           */}
      {/* ---------------------------------------------------------------- */}
      <aside
        data-slot="app-shell-sidebar"
        className="app-shell__sidebar border-r border-border-subtle bg-surface-secondary overflow-y-auto"
      >
        {sidebar}
      </aside>

      {/* ---------------------------------------------------------------- */}
      {/* Main content / canvas                                             */}
      {/* ---------------------------------------------------------------- */}
      <main
        data-slot="app-shell-main"
        className="app-shell__main bg-surface-primary"
      >
        {main}
      </main>

      {/* ---------------------------------------------------------------- */}
      {/* Inspector panel                                                   */}
      {/* ---------------------------------------------------------------- */}
      <aside
        data-slot="app-shell-inspector"
        className="app-shell__inspector border-l border-border-subtle bg-surface-secondary overflow-y-auto"
      >
        {inspector}
      </aside>

      {/* ---------------------------------------------------------------- */}
      {/* Status bar — spans all columns                                    */}
      {/* ---------------------------------------------------------------- */}
      <footer
        data-slot="app-shell-status-bar"
        className="app-shell__status border-t border-border-subtle bg-surface-secondary"
      >
        {statusBar}
      </footer>
    </div>
  )
}
