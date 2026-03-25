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

export const WithBottomPanel: Story = {
  name: "Canvas editor — with bottom panel (collapsed)",
  render: () => (
    <div
      className="app-shell"
      data-sidebar="expanded"
      data-inspector="open"
      data-bottom="collapsed"
      style={{ height: "100vh", display: "grid", gridTemplateRows: "var(--header-height) 1fr 36px", gridTemplateColumns: "auto 1fr auto", gridTemplateAreas: '"header header header" "sidebar main inspector" "bottom bottom bottom"' }}
    >
      <header className="app-shell__header" style={{ borderBottom: "1px solid var(--border-default)", gridArea: "header" }}>
        <Placeholder label="header" />
      </header>
      <aside className="app-shell__sidebar" style={{ gridArea: "sidebar", width: "var(--sidebar-width-expanded)", borderRight: "1px solid var(--border-default)", background: "var(--sidebar-bg)" }}>
        <Placeholder label="sidebar" />
      </aside>
      <main className="app-shell__main" style={{ gridArea: "main" }}>
        <Placeholder label="main canvas" />
      </main>
      <aside className="app-shell__inspector" style={{ gridArea: "inspector", width: "var(--inspector-width)", borderLeft: "1px solid var(--border-default)", background: "var(--surface-secondary)" }}>
        <Placeholder label="inspector" />
      </aside>
      {/* Bottom panel — 36px collapsed, tabs visible, full-width above sidebars */}
      <div style={{ gridArea: "bottom", background: "var(--surface-secondary)", borderTop: "1px solid var(--border-subtle)", display: "flex", flexDirection: "column", minHeight: "36px", zIndex: 10, position: "relative" }}>
        <div style={{ display: "flex", alignItems: "center", height: "36px", padding: "0 var(--space-3)", gap: "var(--space-4)", flexShrink: 0 }}>
          <button style={{ fontFamily: "var(--font-body)", fontSize: "var(--font-size-xs)", fontWeight: "var(--font-weight-medium)", color: "var(--text-heading)", background: "none", border: "none", cursor: "pointer", padding: "var(--space-2) 0", borderBottom: "2px solid var(--interactive-default)" }}>
            Logs
          </button>
          <button style={{ fontFamily: "var(--font-body)", fontSize: "var(--font-size-xs)", fontWeight: "var(--font-weight-medium)", color: "var(--text-muted)", background: "none", border: "none", cursor: "pointer", padding: "var(--space-2) 0", borderBottom: "2px solid transparent" }}>
            Artifacts
          </button>
          <button style={{ marginLeft: "auto", width: 28, height: 28, display: "flex", alignItems: "center", justifyContent: "center", background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", borderRadius: "var(--radius-sm)", fontSize: 12 }} aria-label="Expand panel">
            ▲
          </button>
        </div>
      </div>
    </div>
  ),
};

export const WithBottomPanelExpanded: Story = {
  name: "Canvas editor — with bottom panel (expanded, 200px)",
  render: () => (
    <div
      className="app-shell"
      data-sidebar="expanded"
      data-inspector="open"
      data-bottom="expanded"
      style={{ height: "100vh", display: "grid", gridTemplateRows: "var(--header-height) 1fr 200px", gridTemplateColumns: "auto 1fr auto", gridTemplateAreas: '"header header header" "sidebar main inspector" "bottom bottom bottom"' }}
    >
      <header className="app-shell__header" style={{ borderBottom: "1px solid var(--border-default)", gridArea: "header" }}>
        <Placeholder label="header" />
      </header>
      <aside className="app-shell__sidebar" style={{ gridArea: "sidebar", width: "var(--sidebar-width-expanded)", borderRight: "1px solid var(--border-default)", background: "var(--sidebar-bg)" }}>
        <Placeholder label="sidebar" />
      </aside>
      <main className="app-shell__main" style={{ gridArea: "main" }}>
        <Placeholder label="main canvas" />
      </main>
      <aside className="app-shell__inspector" style={{ gridArea: "inspector", width: "var(--inspector-width)", borderLeft: "1px solid var(--border-default)", background: "var(--surface-secondary)" }}>
        <Placeholder label="inspector" />
      </aside>
      {/* Bottom panel — 200px expanded, content visible, full-width above sidebars */}
      <div style={{ gridArea: "bottom", background: "var(--surface-secondary)", borderTop: "1px solid var(--border-subtle)", display: "flex", flexDirection: "column", overflow: "hidden", zIndex: 10, position: "relative" }}>
        <div style={{ display: "flex", alignItems: "center", height: "36px", padding: "0 var(--space-3)", gap: "var(--space-4)", flexShrink: 0 }}>
          <button style={{ fontFamily: "var(--font-body)", fontSize: "var(--font-size-xs)", fontWeight: "var(--font-weight-medium)", color: "var(--text-heading)", background: "none", border: "none", cursor: "pointer", padding: "var(--space-2) 0", borderBottom: "2px solid var(--interactive-default)" }}>
            Logs
          </button>
          <button style={{ fontFamily: "var(--font-body)", fontSize: "var(--font-size-xs)", fontWeight: "var(--font-weight-medium)", color: "var(--text-muted)", background: "none", border: "none", cursor: "pointer", padding: "var(--space-2) 0", borderBottom: "2px solid transparent" }}>
            Artifacts
          </button>
          <button style={{ marginLeft: "auto", width: 28, height: 28, display: "flex", alignItems: "center", justifyContent: "center", background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", borderRadius: "var(--radius-sm)", fontSize: 12 }} aria-label="Collapse panel">
            ▼
          </button>
        </div>
        <div style={{ flex: 1, overflowY: "auto", padding: "var(--space-2) var(--space-3)", fontFamily: "var(--font-mono)", fontSize: "var(--font-size-xs)", color: "var(--text-muted)", display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
          <div style={{ display: "flex", gap: "var(--space-2)" }}><span style={{ color: "var(--text-muted)", minWidth: 70, fontSize: "var(--font-size-2xs)" }}>09:14:03.221</span><span style={{ color: "var(--success-9)" }}>✓</span><span>research_agent — completed in 12.3s</span></div>
          <div style={{ display: "flex", gap: "var(--space-2)" }}><span style={{ color: "var(--text-muted)", minWidth: 70, fontSize: "var(--font-size-2xs)" }}>09:14:04.558</span><span style={{ color: "var(--info-9)" }}>→</span><span>summarise_results — running</span></div>
          <div style={{ display: "flex", gap: "var(--space-2)" }}><span style={{ color: "var(--text-muted)", minWidth: 70, fontSize: "var(--font-size-2xs)" }}>09:14:05.001</span><span style={{ color: "var(--text-muted)" }}>·</span><span style={{ color: "var(--text-muted)" }}>tokens: 1,842 / cost: $0.0023</span></div>
        </div>
      </div>
    </div>
  ),
};
