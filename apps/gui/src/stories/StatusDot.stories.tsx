import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { StatusDot } from "@/components/ui/status-dot";

const meta: Meta<typeof StatusDot> = {
  title: "Primitives/StatusDot",
  component: StatusDot,
  parameters: { layout: "centered" },
  argTypes: {
    variant: {
      control: { type: "select" },
      options: ["neutral", "active", "success", "warning", "danger"],
      description: "Semantic color variant of the status dot",
    },
    animate: {
      control: { type: "select" },
      options: ["none", "pulse", "spin"],
      description: "Animation applied to the status dot",
    },
  },
};
export default meta;

type Story = StoryObj<typeof StatusDot>;

export const Default: Story = {
  name: "Default (controls)",
  args: {
    variant: "active",
    animate: "pulse",
  },
};

export const AllVariants: Story = {
  name: "All Variants",
  render: () => (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)", padding: "var(--space-4)" }}>
      <StatusDot variant="neutral" />
      <StatusDot variant="active" />
      <StatusDot variant="success" />
      <StatusDot variant="warning" />
      <StatusDot variant="danger" />
    </div>
  ),
};

export const AllAnimations: Story = {
  name: "All Animations",
  render: () => (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-6)", padding: "var(--space-4)" }}>
      <StatusDot variant="success" animate="none" />
      <StatusDot variant="active" animate="pulse" />
      <StatusDot variant="warning" animate="spin" />
    </div>
  ),
};
