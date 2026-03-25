import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Primitives/StatusDot",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

export const Neutral: Story = {
  name: "Variant: neutral",
  render: () => <span className="status-dot status-dot--neutral" />,
};

export const Active: Story = {
  name: "Variant: active",
  render: () => <span className="status-dot status-dot--active" />,
};

export const Success: Story = {
  name: "Variant: success",
  render: () => <span className="status-dot status-dot--success" />,
};

export const Warning: Story = {
  name: "Variant: warning",
  render: () => <span className="status-dot status-dot--warning" />,
};

export const Danger: Story = {
  name: "Variant: danger",
  render: () => <span className="status-dot status-dot--danger" />,
};

export const Pulse: Story = {
  name: "Animation: pulse",
  render: () => <span className="status-dot status-dot--active status-dot--pulse" />,
};

export const Spin: Story = {
  name: "Animation: spin",
  render: () => <span className="status-dot status-dot--warning status-dot--spin" />,
};

export const AllVariants: Story = {
  name: "All Variants",
  render: () => (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)", padding: "var(--space-4)" }}>
      <span className="status-dot status-dot--neutral" />
      <span className="status-dot status-dot--active" />
      <span className="status-dot status-dot--success" />
      <span className="status-dot status-dot--warning" />
      <span className="status-dot status-dot--danger" />
    </div>
  ),
};

export const AllAnimations: Story = {
  name: "All Animations (pulse + spin)",
  render: () => (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-6)", padding: "var(--space-4)" }}>
      <span className="status-dot status-dot--active status-dot--pulse" />
      <span className="status-dot status-dot--warning status-dot--spin" />
      <span className="status-dot status-dot--success" />
    </div>
  ),
};
