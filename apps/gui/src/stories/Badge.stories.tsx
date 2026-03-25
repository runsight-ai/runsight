import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Primitives/Badge",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

export const Accent: Story = {
  render: () => <span className="badge badge--accent">Accent</span>,
};

export const Success: Story = {
  render: () => <span className="badge badge--success">Active</span>,
};

export const Warning: Story = {
  render: () => <span className="badge badge--warning">Pending</span>,
};

export const Danger: Story = {
  render: () => <span className="badge badge--danger">Failed</span>,
};

export const Info: Story = {
  render: () => <span className="badge badge--info">Info</span>,
};

export const Neutral: Story = {
  render: () => <span className="badge badge--neutral">Draft</span>,
};

export const Outline: Story = {
  render: () => <span className="badge badge--outline">v0.4.2</span>,
};

export const WithDot: Story = {
  name: "With Dot Indicator",
  render: () => (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
      <span className="badge badge--success">
        <span className="badge__dot" />
        Online
      </span>
      <span className="badge badge--warning">
        <span className="badge__dot" />
        Pending
      </span>
      <span className="badge badge--danger">
        <span className="badge__dot" />
        Failed
      </span>
    </div>
  ),
};

export const AllVariants: Story = {
  render: () => (
    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "var(--space-2)" }}>
      <span className="badge badge--accent">Accent</span>
      <span className="badge badge--success">Success</span>
      <span className="badge badge--warning">Warning</span>
      <span className="badge badge--danger">Danger</span>
      <span className="badge badge--info">Info</span>
      <span className="badge badge--neutral">Neutral</span>
      <span className="badge badge--outline">Outline</span>
    </div>
  ),
};
