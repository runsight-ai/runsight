import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Primitives/Progress",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <div className="progress" style={{ width: "280px" }}>
      <div className="progress__fill" style={{ width: "60%" }} />
    </div>
  ),
};

export const Medium: Story = {
  name: "Variant: md",
  render: () => (
    <div className="progress progress--md" style={{ width: "280px" }}>
      <div className="progress__fill" style={{ width: "40%" }} />
    </div>
  ),
};

export const Success: Story = {
  name: "Variant: success",
  render: () => (
    <div className="progress progress--md progress--success" style={{ width: "280px" }}>
      <div className="progress__fill" style={{ width: "100%" }} />
    </div>
  ),
};

export const Danger: Story = {
  name: "Variant: danger",
  render: () => (
    <div className="progress progress--md progress--danger" style={{ width: "280px" }}>
      <div className="progress__fill" style={{ width: "25%" }} />
    </div>
  ),
};

export const Indeterminate: Story = {
  name: "Variant: indeterminate",
  render: () => (
    <div className="progress progress--indeterminate" style={{ width: "280px" }}>
      <div className="progress__fill" />
    </div>
  ),
};

export const AllVariants: Story = {
  name: "All Variants",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)", padding: "var(--space-4)", width: "320px" }}>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
        <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>Default (60%)</span>
        <div className="progress">
          <div className="progress__fill" style={{ width: "60%" }} />
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
        <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>Success (100%)</span>
        <div className="progress progress--success">
          <div className="progress__fill" style={{ width: "100%" }} />
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
        <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>Danger (25%)</span>
        <div className="progress progress--danger">
          <div className="progress__fill" style={{ width: "25%" }} />
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
        <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>Indeterminate</span>
        <div className="progress progress--indeterminate">
          <div className="progress__fill" />
        </div>
      </div>
    </div>
  ),
};
