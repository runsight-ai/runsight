import type { Meta, StoryObj } from "@storybook/react"
import React from "react"

import { Badge } from "@/components/ui/badge"
import { Sidebar } from "@/components/ui/sidebar"
import type { SidebarNavItem, SidebarSection } from "@/components/ui/sidebar"

// --- Icon helpers (inline SVG, no external dep) ---

const DashboardIcon = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="7" height="9" />
    <rect x="14" y="3" width="7" height="5" />
    <rect x="14" y="12" width="7" height="9" />
    <rect x="3" y="16" width="7" height="5" />
  </svg>
)

const WorkflowIcon = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
  </svg>
)

const RunsIcon = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 20V10M18 20V4M6 20v-4" />
  </svg>
)

const ProvidersIcon = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z" />
  </svg>
)

const RunsightLogo = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
    <circle cx="12" cy="5" r="2.5" fill="var(--interactive-default)" />
    <circle cx="5" cy="17" r="2.5" fill="var(--interactive-default)" opacity="0.7" />
    <circle cx="19" cy="17" r="2.5" fill="var(--interactive-default)" opacity="0.7" />
    <circle cx="12" cy="13" r="1.5" fill="var(--interactive-default)" opacity="0.5" />
    <line x1="12" y1="7.5" x2="12" y2="11.5" stroke="var(--interactive-default)" strokeWidth="1.5" strokeLinecap="round" />
    <line x1="10.8" y1="14" x2="6.5" y2="15.5" stroke="var(--interactive-default)" strokeWidth="1.5" strokeLinecap="round" opacity="0.6" />
    <line x1="13.2" y1="14" x2="17.5" y2="15.5" stroke="var(--interactive-default)" strokeWidth="1.5" strokeLinecap="round" opacity="0.6" />
  </svg>
)

// --- Data ---

const defaultSections: SidebarSection[] = [
  { id: "main" },
  { id: "system", label: "System" },
]

const defaultItems: SidebarNavItem[] = [
  { id: "dashboard", label: "Dashboard", icon: <DashboardIcon />, section: "main" },
  {
    id: "workflows",
    label: "Workflows",
    icon: <WorkflowIcon />,
    badge: <Badge variant="neutral">12</Badge>,
    section: "main",
  },
  { id: "runs", label: "Runs", icon: <RunsIcon />, section: "main" },
  { id: "providers", label: "Providers", icon: <ProvidersIcon />, section: "system" },
]

const logoSlot = (
  <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", height: "var(--control-height-md)", padding: "0 var(--space-2)" }}>
    <RunsightLogo />
    <span style={{ fontSize: "var(--font-size-sm)", fontWeight: "var(--font-weight-semibold)", letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-primary)" }}>
      Runsight
    </span>
  </div>
)

// --- Meta ---

const meta: Meta<typeof Sidebar> = {
  title: "Navigation/Sidebar",
  component: Sidebar,
  parameters: { layout: "centered" },
  argTypes: {
    collapsed: {
      control: "boolean",
      description: "Toggle collapsed (icon-rail) mode",
    },
    activeId: {
      control: { type: "select" },
      options: ["dashboard", "workflows", "runs", "providers"],
      description: "Active navigation item id",
    },
  },
}
export default meta

type Story = StoryObj<typeof Sidebar>

export const Default: Story = {
  name: "Default (controls)",
  args: {
    collapsed: false,
    activeId: "workflows",
    items: defaultItems,
    sections: defaultSections,
    logo: logoSlot,
  },
  render: (args) => (
    <div style={{ height: 400 }}>
      <Sidebar {...args} />
    </div>
  ),
}

export const Collapsed: Story = {
  name: "Collapsed",
  render: () => (
    <div style={{ height: 400 }}>
      <Sidebar
        collapsed
        activeId="workflows"
        items={defaultItems}
        sections={defaultSections}
        logo={logoSlot}
      />
    </div>
  ),
}

export const WithSections: Story = {
  name: "With Sections",
  render: () => (
    <div style={{ height: 400 }}>
      <Sidebar
        collapsed={false}
        activeId="dashboard"
        items={defaultItems}
        sections={defaultSections}
        logo={logoSlot}
      />
    </div>
  ),
}
