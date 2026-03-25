import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

type StatusDotVariant = "neutral" | "active" | "success" | "warning" | "danger";
type StatusDotAnimation = "none" | "pulse" | "spin";

interface StatusDotProps {
  variant: StatusDotVariant;
  animation: StatusDotAnimation;
}

function StatusDotComponent({ variant, animation }: StatusDotProps) {
  const classes = [
    "status-dot",
    `status-dot--${variant}`,
    animation !== "none" ? `status-dot--${animation}` : "",
  ].filter(Boolean).join(" ");
  return <span className={classes} />;
}

const meta: Meta<StatusDotProps> = {
  title: "Primitives/StatusDot",
  component: StatusDotComponent,
  parameters: { layout: "centered" },
  argTypes: {
    variant: {
      control: { type: "select" },
      options: ["neutral", "active", "success", "warning", "danger"],
    },
    animation: {
      control: { type: "select" },
      options: ["none", "pulse", "spin"],
    },
  },
};
export default meta;

type Story = StoryObj<StatusDotProps>;

export const Default: Story = {
  name: "Default (controls)",
  args: {
    variant: "active",
    animation: "pulse",
  },
  render: (args) => <StatusDotComponent variant={args.variant} animation={args.animation} />,
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
