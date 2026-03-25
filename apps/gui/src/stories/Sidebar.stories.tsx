import type { Meta, StoryObj } from "@storybook/react";
import React, { useState } from "react";

const meta = {
  title: "Navigation/Sidebar",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

const DashboardIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
  </svg>
);

const WorkflowIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
    <path d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
  </svg>
);

const BotIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
    <path d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
  </svg>
);

const PlayIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
    <path d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
  </svg>
);

const SettingsIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
    <path d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
    <path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
  </svg>
);

function SidebarDemo({ collapsed = false }: { collapsed?: boolean }) {
  const [isCollapsed, setIsCollapsed] = useState(collapsed);
  const navItems = [
    { icon: <DashboardIcon />, label: "Dashboard" },
    { icon: <WorkflowIcon />, label: "Workflows", active: true },
    { icon: <BotIcon />, label: "Souls" },
    { icon: <PlayIcon />, label: "Runs" },
  ];

  return (
    <div className={`sidebar${isCollapsed ? " sidebar--collapsed" : ""}`} style={{ height: "480px" }}>
      <div className="sidebar__section" style={{ borderBottom: "1px solid var(--sidebar-border)", paddingTop: "var(--space-2)", paddingBottom: "var(--space-2)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", height: "var(--control-height-md)", padding: "0 var(--space-2)" }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
            <circle cx="12" cy="5" r="2.5" fill="var(--interactive-default)" />
            <circle cx="5" cy="17" r="2.5" fill="var(--interactive-default)" opacity="0.7" />
            <circle cx="19" cy="17" r="2.5" fill="var(--interactive-default)" opacity="0.7" />
          </svg>
          <span className="sidebar__item-label" style={{ fontSize: "var(--font-size-sm)", fontWeight: "var(--font-weight-semibold)", letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-primary)" }}>
            Runsight
          </span>
        </div>
      </div>

      <div className="sidebar__section" style={{ flex: 1 }}>
        {navItems.map(({ icon, label, active }) => (
          <div key={label} className={`sidebar__item${active ? " sidebar__item--active" : ""}`} role="menuitem" tabIndex={0}>
            <span className="sidebar__item-icon">{icon}</span>
            <span className="sidebar__item-label">{label}</span>
          </div>
        ))}
      </div>

      <div className="sidebar__section" style={{ borderTop: "1px solid var(--sidebar-border)" }}>
        <div className="sidebar__item" role="menuitem">
          <span className="sidebar__item-icon"><SettingsIcon /></span>
          <span className="sidebar__item-label">Settings</span>
        </div>
        <button className="sidebar__item" style={{ width: "100%", background: "none", border: "none", textAlign: "left", cursor: "pointer" }} onClick={() => setIsCollapsed(!isCollapsed)}>
          <span className="sidebar__item-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
              <path d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25H12" />
            </svg>
          </span>
          <span className="sidebar__item-label">{isCollapsed ? "Expand" : "Collapse"}</span>
        </button>
      </div>
    </div>
  );
}

export const Expanded: Story = {
  render: () => <SidebarDemo collapsed={false} />,
};

export const Collapsed: Story = {
  render: () => <SidebarDemo collapsed={true} />,
};

export const Interactive: Story = {
  render: () => <SidebarDemo collapsed={false} />,
};
