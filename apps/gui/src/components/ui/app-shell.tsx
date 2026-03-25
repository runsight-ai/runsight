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
// CSS custom-property constants (matching globals.css panel tokens)
// These are referenced as CSS variables so Tailwind's JIT can't strip them;
// they are used in inline style objects to apply exact token values.
// ---------------------------------------------------------------------------

const HEADER_HEIGHT         = "var(--header-height)"          // 40px
const STATUS_BAR_HEIGHT     = "var(--status-bar-height)"      // 22px
const SIDEBAR_WIDTH_COLLAPSED = "var(--sidebar-width-collapsed)" // 48px
const SIDEBAR_WIDTH_EXPANDED  = "var(--sidebar-width-expanded)"  // 240px
const INSPECTOR_WIDTH       = "var(--inspector-width)"        // 320px
const INSPECTOR_WIDTH_MIN   = "var(--inspector-width-min)"    // 240px
const INSPECTOR_WIDTH_MAX   = "var(--inspector-width-max)"    // 480px

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
  const sidebarWidth = sidebarCollapsed
    ? SIDEBAR_WIDTH_COLLAPSED
    : SIDEBAR_WIDTH_EXPANDED

  const gridTemplateColumns = inspectorOpen
    ? `${sidebarWidth} 1fr ${INSPECTOR_WIDTH}`
    : `${sidebarWidth} 1fr`

  const gridTemplateRows = `${HEADER_HEIGHT} 1fr ${STATUS_BAR_HEIGHT}`

  return (
    <div
      data-slot="app-shell"
      data-sidebar-collapsed={sidebarCollapsed || undefined}
      data-inspector-open={inspectorOpen || undefined}
      className={cn("grid h-screen w-full overflow-hidden", className)}
      style={{
        // CSS Grid — panel sizes driven by design-system tokens
        display: "grid",
        gridTemplateRows,
        gridTemplateColumns,
        // Expose panel-size tokens as CSS props for child consumer use
        "--header-height":            HEADER_HEIGHT,
        "--status-bar-height":        STATUS_BAR_HEIGHT,
        "--sidebar-width-collapsed":  SIDEBAR_WIDTH_COLLAPSED,
        "--sidebar-width-expanded":   SIDEBAR_WIDTH_EXPANDED,
        "--inspector-width":          INSPECTOR_WIDTH,
        "--inspector-width-min":      INSPECTOR_WIDTH_MIN,
        "--inspector-width-max":      INSPECTOR_WIDTH_MAX,
      } as React.CSSProperties}
    >
      {/* ---------------------------------------------------------------- */}
      {/* Header — spans all columns                                        */}
      {/* ---------------------------------------------------------------- */}
      <header
        data-slot="app-shell-header"
        className="border-b border-border-subtle bg-surface-secondary"
        style={{
          gridColumn: "1 / -1",
          gridRow: "1",
          height: HEADER_HEIGHT,
        }}
      >
        {header}
      </header>

      {/* ---------------------------------------------------------------- */}
      {/* Sidebar                                                           */}
      {/* ---------------------------------------------------------------- */}
      <aside
        data-slot="app-shell-sidebar"
        className="border-r border-border-subtle bg-surface-secondary overflow-y-auto"
        style={{
          gridColumn: "1",
          gridRow: "2",
          width: sidebarWidth,
          minWidth: sidebarCollapsed
            ? SIDEBAR_WIDTH_COLLAPSED
            : SIDEBAR_WIDTH_COLLAPSED,
          maxWidth: SIDEBAR_WIDTH_EXPANDED,
        }}
      >
        {sidebar}
      </aside>

      {/* ---------------------------------------------------------------- */}
      {/* Main content / canvas                                             */}
      {/* ---------------------------------------------------------------- */}
      <main
        data-slot="app-shell-main"
        className="relative overflow-hidden bg-surface-primary"
        style={{
          gridColumn: "2",
          gridRow: "2",
        }}
      >
        {main}
      </main>

      {/* ---------------------------------------------------------------- */}
      {/* Inspector panel (conditionally rendered)                          */}
      {/* ---------------------------------------------------------------- */}
      {inspectorOpen && (
        <aside
          data-slot="app-shell-inspector"
          className="border-l border-border-subtle bg-surface-secondary overflow-y-auto"
          style={{
            gridColumn: "3",
            gridRow: "2",
            width: INSPECTOR_WIDTH,
            minWidth: INSPECTOR_WIDTH_MIN,
            maxWidth: INSPECTOR_WIDTH_MAX,
          }}
        >
          {inspector}
        </aside>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* Status bar — spans all columns                                    */}
      {/* ---------------------------------------------------------------- */}
      <footer
        data-slot="app-shell-status-bar"
        className="border-t border-border-subtle bg-surface-secondary"
        style={{
          gridColumn: "1 / -1",
          gridRow: "3",
          height: STATUS_BAR_HEIGHT,
        }}
      >
        {statusBar}
      </footer>
    </div>
  )
}
