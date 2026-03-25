import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Composites/AppShell",
  parameters: { layout: "fullscreen" },
};
export default meta;

type Story = StoryObj;

function Placeholder({ label, muted = false }: { label: string; muted?: boolean }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "center",
      width: "100%", height: "100%", padding: "8px",
      opacity: muted ? 0.4 : 0.7, fontSize: 11,
      fontFamily: "var(--font-mono)", color: "var(--text-muted)",
      border: "1px dashed var(--border-subtle)", boxSizing: "border-box",
    }}>
      {label}
    </div>
  );
}

export const Default: Story = {
  render: () => (
    <div className="app-shell" data-sidebar="expanded" data-inspector="open" style={{ height: "100vh" }}>
      <header className="app-shell__header" style={{ borderBottom: "1px solid var(--border-default)" }}>
        <Placeholder label="header" />
      </header>
      <aside className="app-shell__sidebar" style={{ width: "var(--sidebar-width-expanded)", borderRight: "1px solid var(--border-default)", background: "var(--sidebar-bg)" }}>
        <Placeholder label="sidebar" />
      </aside>
      <main className="app-shell__main">
        <Placeholder label="main canvas" />
      </main>
      <aside className="app-shell__inspector" style={{ width: "var(--inspector-width)", borderLeft: "1px solid var(--border-default)", background: "var(--surface-secondary)" }}>
        <Placeholder label="inspector" />
      </aside>
      <div className="app-shell__status" style={{ borderTop: "1px solid var(--border-subtle)", background: "var(--surface-secondary)" }}>
        <Placeholder label="status bar" muted />
      </div>
    </div>
  ),
};

export const SidebarCollapsed: Story = {
  name: "Sidebar — collapsed",
  render: () => (
    <div className="app-shell" data-sidebar="collapsed" data-inspector="open" style={{ height: "100vh" }}>
      <header className="app-shell__header" style={{ borderBottom: "1px solid var(--border-default)" }}>
        <Placeholder label="header" />
      </header>
      <aside className="app-shell__sidebar" style={{ width: "var(--sidebar-width-collapsed)", borderRight: "1px solid var(--border-default)", background: "var(--sidebar-bg)" }}>
        <Placeholder label="·" />
      </aside>
      <main className="app-shell__main">
        <Placeholder label="main canvas" />
      </main>
      <aside className="app-shell__inspector" style={{ width: "var(--inspector-width)", borderLeft: "1px solid var(--border-default)", background: "var(--surface-secondary)" }}>
        <Placeholder label="inspector" />
      </aside>
      <div className="app-shell__status" style={{ borderTop: "1px solid var(--border-subtle)", background: "var(--surface-secondary)" }}>
        <Placeholder label="status bar" muted />
      </div>
    </div>
  ),
};

export const InspectorClosed: Story = {
  name: "Inspector — hidden",
  render: () => (
    <div className="app-shell" data-sidebar="expanded" data-inspector="closed" style={{ height: "100vh" }}>
      <header className="app-shell__header" style={{ borderBottom: "1px solid var(--border-default)" }}>
        <Placeholder label="header" />
      </header>
      <aside className="app-shell__sidebar" style={{ width: "var(--sidebar-width-expanded)", borderRight: "1px solid var(--border-default)", background: "var(--sidebar-bg)" }}>
        <Placeholder label="sidebar" />
      </aside>
      <main className="app-shell__main">
        <Placeholder label="main canvas (full width)" />
      </main>
      <div className="app-shell__status" style={{ borderTop: "1px solid var(--border-subtle)", background: "var(--surface-secondary)" }}>
        <Placeholder label="status bar" muted />
      </div>
    </div>
  ),
};

export const FocusMode: Story = {
  name: "Focus mode (sidebar collapsed + inspector closed)",
  render: () => (
    <div className="app-shell" data-sidebar="collapsed" data-inspector="closed" style={{ height: "100vh" }}>
      <header className="app-shell__header" style={{ borderBottom: "1px solid var(--border-default)" }}>
        <Placeholder label="header" />
      </header>
      <aside className="app-shell__sidebar" style={{ width: "var(--sidebar-width-collapsed)", borderRight: "1px solid var(--border-default)", background: "var(--sidebar-bg)" }}>
        <Placeholder label="·" />
      </aside>
      <main className="app-shell__main">
        <Placeholder label="main canvas (maximized)" />
      </main>
      <div className="app-shell__status" style={{ borderTop: "1px solid var(--border-subtle)", background: "var(--surface-secondary)" }}>
        <Placeholder label="status bar" muted />
      </div>
    </div>
  ),
};
