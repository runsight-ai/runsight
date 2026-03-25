import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { Badge, BadgeDot } from "@/components/ui/badge";

const meta: Meta<typeof Badge> = {
  title: "Primitives/Badge",
  component: Badge,
  parameters: { layout: "centered" },
  argTypes: {
    variant: {
      control: { type: "select" },
      options: ["accent", "success", "warning", "danger", "info", "neutral", "outline"],
    },
    children: { control: "text" },
  },
};
export default meta;

type Story = StoryObj<typeof Badge>;

export const Default: Story = {
  name: "Default (controls)",
  args: {
    variant: "accent",
    children: "Accent",
  },
};

export const AllVariants: Story = {
  name: "All Variants",
  render: () => (
    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "var(--space-2)" }}>
      <Badge variant="accent">Accent</Badge>
      <Badge variant="success">Success</Badge>
      <Badge variant="warning">Warning</Badge>
      <Badge variant="danger">Danger</Badge>
      <Badge variant="info">Info</Badge>
      <Badge variant="neutral">Neutral</Badge>
      <Badge variant="outline">Outline</Badge>
    </div>
  ),
};

export const WithDot: Story = {
  name: "With Dot Indicator",
  render: () => (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
      <Badge variant="success"><BadgeDot />Online</Badge>
      <Badge variant="warning"><BadgeDot />Pending</Badge>
      <Badge variant="danger"><BadgeDot />Failed</Badge>
    </div>
  ),
};
