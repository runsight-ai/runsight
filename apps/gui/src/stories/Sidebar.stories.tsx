import type { Meta, StoryObj } from "@storybook/react"
import React, { useState } from "react"
import {
  LayoutDashboard,
  Workflow,
  Bot,
  Play,
  Settings,
  PanelLeftClose,
  PanelLeft,
} from "lucide-react"
import { cn } from "@/utils/helpers"

// ---------------------------------------------------------------------------
// Inline sidebar demo component (no router dependency)
// ---------------------------------------------------------------------------

const NAV_ITEMS = [
  { icon: LayoutDashboard, label: "Dashboard" },
  { icon: Workflow, label: "Workflows", active: true },
  { icon: Bot, label: "Souls" },
  { icon: Play, label: "Runs" },
]

interface SidebarDemoProps {
  defaultOpen?: boolean
}

function SidebarDemo({ defaultOpen = true }: SidebarDemoProps) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <aside
      style={{
        backgroundColor: "var(--sidebar-bg)",
        width: open ? "var(--sidebar-width-expanded)" : "var(--sidebar-width-collapsed)",
        transition: "width 200ms ease",
      }}
      className="flex flex-col border-r border-sidebar-border h-[480px]"
    >
      {/* Logo row */}
      <div className="h-12 px-3 border-b border-sidebar-border flex items-center gap-2 shrink-0">
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          className="shrink-0"
        >
          <circle cx="12" cy="5" r="2.5" fill="var(--interactive-default)" />
          <circle cx="5" cy="17" r="2.5" fill="var(--interactive-default)" opacity="0.7" />
          <circle cx="19" cy="17" r="2.5" fill="var(--interactive-default)" opacity="0.7" />
        </svg>
        {open && (
          <span className="text-[13px] font-semibold tracking-[0.08em] uppercase text-primary">
            Runsight
          </span>
        )}
      </div>

      {/* Nav items */}
      <nav className="flex-1 py-2 px-2 overflow-y-auto">
        {NAV_ITEMS.map(({ icon: Icon, label, active }) => (
          <div
            key={label}
            style={active ? { backgroundColor: "var(--sidebar-active-indicator)" } : {}}
            className={cn(
              "flex items-center gap-3 h-9 px-3 rounded-md text-sm transition-colors cursor-pointer",
              active ? "text-primary" : "text-muted hover:text-primary",
            )}
            onMouseEnter={(e) => {
              if (!active) {
                (e.currentTarget as HTMLElement).style.backgroundColor = "var(--sidebar-hover)"
              }
            }}
            onMouseLeave={(e) => {
              if (!active) {
                (e.currentTarget as HTMLElement).style.backgroundColor = ""
              }
            }}
          >
            <Icon
              style={{ width: "var(--icon-size-md)", height: "var(--icon-size-md)" }}
              className="shrink-0"
              strokeWidth={1.5}
            />
            {open && <span>{label}</span>}
          </div>
        ))}
      </nav>

      {/* Bottom nav */}
      <div className="p-2 border-t border-sidebar-border">
        <div
          className="flex items-center gap-3 h-9 px-3 rounded-md text-sm text-muted hover:text-primary cursor-pointer transition-colors"
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLElement).style.backgroundColor = "var(--sidebar-hover)"
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLElement).style.backgroundColor = ""
          }}
        >
          <Settings
            style={{ width: "var(--icon-size-md)", height: "var(--icon-size-md)" }}
            className="shrink-0"
            strokeWidth={1.5}
          />
          {open && <span>Settings</span>}
        </div>

        {/* Toggle button */}
        <button
          onClick={() => setOpen((prev) => !prev)}
          className="mt-1 flex items-center gap-3 h-9 w-full px-3 rounded-md text-sm text-muted hover:text-primary transition-colors"
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLElement).style.backgroundColor = "var(--sidebar-hover)"
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLElement).style.backgroundColor = ""
          }}
        >
          {open ? (
            <PanelLeftClose
              style={{ width: "var(--icon-size-md)", height: "var(--icon-size-md)" }}
              strokeWidth={1.5}
            />
          ) : (
            <PanelLeft
              style={{ width: "var(--icon-size-md)", height: "var(--icon-size-md)" }}
              strokeWidth={1.5}
            />
          )}
          {open && <span>Collapse</span>}
        </button>
      </div>
    </aside>
  )
}

// ---------------------------------------------------------------------------
// Meta
// ---------------------------------------------------------------------------

const meta: Meta = {
  title: "Navigation/Sidebar",
  parameters: {
    layout: "centered",
  },
}

export default meta

type Story = StoryObj

// ---------------------------------------------------------------------------
// Stories
// ---------------------------------------------------------------------------

export const Expanded: Story = {
  render: () => <SidebarDemo defaultOpen={true} />,
}

export const Collapsed: Story = {
  render: () => <SidebarDemo defaultOpen={false} />,
}

export const Interactive: Story = {
  render: () => <SidebarDemo defaultOpen={true} />,
}
