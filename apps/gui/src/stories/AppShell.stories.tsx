import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { AppShell } from "@/components/ui/app-shell";

const meta: Meta<typeof AppShell> = {
  title: "Composites/AppShell",
  component: AppShell,
  parameters: {
    layout: "fullscreen",
  },
  argTypes: {
    sidebarCollapsed: { control: "boolean" },
    inspectorOpen:    { control: "boolean" },
  },
};

export default meta;

type Story = StoryObj<typeof AppShell>;

// ---------------------------------------------------------------------------
// Placeholder helpers
// ---------------------------------------------------------------------------

function Placeholder({
  label,
  muted = false,
}: {
  label: string;
  muted?: boolean;
}) {
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
        fontFamily: "monospace",
        color: "var(--text-muted)",
        border: "1px dashed var(--border-subtle)",
        boxSizing: "border-box",
      }}
    >
      {label}
    </div>
  );
}

const sharedSlots = {
  header:    <Placeholder label="header" />,
  sidebar:   <Placeholder label="sidebar" />,
  main:      <Placeholder label="main canvas" />,
  inspector: <Placeholder label="inspector" />,
  statusBar: <Placeholder label="status bar" muted />,
};

// ---------------------------------------------------------------------------
// Default (expanded sidebar + inspector open)
// ---------------------------------------------------------------------------

export const Default: Story = {
  args: {
    sidebarCollapsed: false,
    inspectorOpen: true,
    ...sharedSlots,
  },
};

// ---------------------------------------------------------------------------
// Sidebar collapsed
// ---------------------------------------------------------------------------

export const SidebarCollapsed: Story = {
  name: "Sidebar — collapsed",
  args: {
    sidebarCollapsed: true,
    inspectorOpen: true,
    ...sharedSlots,
  },
};

// ---------------------------------------------------------------------------
// Sidebar expanded
// ---------------------------------------------------------------------------

export const SidebarExpanded: Story = {
  name: "Sidebar — expanded",
  args: {
    sidebarCollapsed: false,
    inspectorOpen: true,
    ...sharedSlots,
  },
};

// ---------------------------------------------------------------------------
// Inspector open
// ---------------------------------------------------------------------------

export const InspectorOpen: Story = {
  name: "Inspector — visible",
  args: {
    sidebarCollapsed: false,
    inspectorOpen: true,
    ...sharedSlots,
  },
};

// ---------------------------------------------------------------------------
// Inspector closed
// ---------------------------------------------------------------------------

export const InspectorClosed: Story = {
  name: "Inspector — hidden",
  args: {
    sidebarCollapsed: false,
    inspectorOpen: false,
    ...sharedSlots,
  },
};

// ---------------------------------------------------------------------------
// Collapsed sidebar + closed inspector (focus mode)
// ---------------------------------------------------------------------------

export const FocusMode: Story = {
  name: "Focus mode (sidebar collapsed + inspector closed)",
  args: {
    sidebarCollapsed: true,
    inspectorOpen: false,
    ...sharedSlots,
  },
};
