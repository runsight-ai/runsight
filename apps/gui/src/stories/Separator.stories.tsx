import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Primitives/Separator",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

export const Horizontal: Story = {
  render: () => (
    <div style={{ width: "256px" }}>
      <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>Above the separator</p>
      <hr className="divider divider--horizontal" style={{ margin: "var(--space-3) 0" }} />
      <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>Below the separator</p>
    </div>
  ),
};

export const Vertical: Story = {
  render: () => (
    <div style={{ display: "flex", alignItems: "center", height: "32px", gap: "var(--space-3)" }}>
      <span style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>Left</span>
      <div className="divider divider--vertical" />
      <span style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>Right</span>
    </div>
  ),
};

export const InToolbar: Story = {
  name: "In Toolbar",
  render: () => (
    <div style={{
      display: "flex", alignItems: "center", gap: "var(--space-2)",
      padding: "0 var(--space-3)", height: "40px",
      borderRadius: "var(--radius-md)", border: "1px solid var(--border-default)"
    }}>
      <button className="btn btn--ghost btn--sm">File</button>
      <button className="btn btn--ghost btn--sm">Edit</button>
      <div className="divider divider--vertical" />
      <button className="btn btn--ghost btn--sm">View</button>
      <div className="divider divider--vertical" />
      <button className="btn btn--ghost btn--sm">Help</button>
    </div>
  ),
};
