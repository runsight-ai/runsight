import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { AppShell } from "@/components/ui/app-shell";

const meta: Meta<typeof AppShell> = {
  title: "Composites/AppShell",
  component: AppShell,
  parameters: { layout: "fullscreen" },
  argTypes: {
    sidebarCollapsed: { control: "boolean" },
    inspectorOpen: { control: "boolean" },
  },
};
export default meta;

type Story = StoryObj<typeof AppShell>;

function Placeholder({ label, muted = false }: { label: string; muted?: boolean }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        width: "100%",
        height: "100%",
        padding: "8px",
        opacity: muted ? 0.4 : 0.7,
        fontSize: 11,
        fontFamily: "var(--font-mono)",
        color: "var(--text-muted)",
        border: "1px dashed var(--border-subtle)",
        boxSizing: "border-box",
      }}
    >
      {label}
    </div>
  );
}

export const Default: Story = {
  name: "Default (controls)",
  args: {
    sidebarCollapsed: false,
    inspectorOpen: true,
  },
  render: (args) => (
    <div style={{ height: "100vh" }}>
      <AppShell
        {...args}
        className="h-full"
        header={<Placeholder label="header" />}
        sidebar={<Placeholder label="sidebar" />}
        main={<Placeholder label="main canvas" />}
        inspector={<Placeholder label="inspector" />}
        statusBar={<Placeholder label="status bar" muted />}
      />
    </div>
  ),
};

export const SidebarCollapsed: Story = {
  name: "Sidebar — collapsed",
  render: () => (
    <div style={{ height: "100vh" }}>
      <AppShell
        sidebarCollapsed
        inspectorOpen
        className="h-full"
        header={<Placeholder label="header" />}
        sidebar={<Placeholder label="·" />}
        main={<Placeholder label="main canvas" />}
        inspector={<Placeholder label="inspector" />}
        statusBar={<Placeholder label="status bar" muted />}
      />
    </div>
  ),
};

export const InspectorClosed: Story = {
  name: "Inspector — hidden",
  render: () => (
    <div style={{ height: "100vh" }}>
      <AppShell
        sidebarCollapsed={false}
        inspectorOpen={false}
        className="h-full"
        header={<Placeholder label="header" />}
        sidebar={<Placeholder label="sidebar" />}
        main={<Placeholder label="main canvas (full width)" />}
        statusBar={<Placeholder label="status bar" muted />}
      />
    </div>
  ),
};

export const WithBottomPanel: Story = {
  name: "With Bottom Panel",
  render: () => (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column" }}>
      <AppShell
        sidebarCollapsed={false}
        inspectorOpen
        className="flex-1 min-h-0"
        header={<Placeholder label="header" />}
        sidebar={<Placeholder label="sidebar" />}
        main={<Placeholder label="main canvas" />}
        inspector={<Placeholder label="inspector" />}
      />
      {/* Bottom panel — collapsed (36px) */}
      <div
        style={{
          background: "var(--surface-secondary)",
          borderTop: "1px solid var(--border-subtle)",
          height: "36px",
          flexShrink: 0,
          display: "flex",
          alignItems: "center",
          padding: "0 var(--space-3)",
          gap: "var(--space-4)",
        }}
      >
        <button
          style={{
            fontFamily: "var(--font-body)",
            fontSize: "var(--font-size-xs)",
            fontWeight: "var(--font-weight-medium)",
            color: "var(--text-heading)",
            background: "none",
            border: "none",
            cursor: "pointer",
            padding: "var(--space-2) 0",
            borderBottom: "2px solid var(--interactive-default)",
          }}
        >
          Logs
        </button>
        <button
          style={{
            fontFamily: "var(--font-body)",
            fontSize: "var(--font-size-xs)",
            fontWeight: "var(--font-weight-medium)",
            color: "var(--text-muted)",
            background: "none",
            border: "none",
            cursor: "pointer",
            padding: "var(--space-2) 0",
            borderBottom: "2px solid transparent",
          }}
        >
          Artifacts
        </button>
        <button
          style={{
            marginLeft: "auto",
            width: 28,
            height: 28,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "none",
            border: "none",
            color: "var(--text-muted)",
            cursor: "pointer",
            borderRadius: "var(--radius-sm)",
            fontSize: 12,
          }}
          aria-label="Expand panel"
        >
          ▲
        </button>
      </div>
    </div>
  ),
};
