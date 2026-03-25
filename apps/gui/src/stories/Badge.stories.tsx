import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { Badge, BadgeDot } from "@/components/ui/badge";

const meta: Meta<typeof Badge> = {
  title: "Primitives/Badge",
  component: Badge,
  parameters: {
    layout: "centered",
  },
  argTypes: {
    variant: {
      control: "select",
      options: ["accent", "success", "warning", "danger", "info", "neutral", "outline"],
    },
  },
};

export default meta;

type Story = StoryObj<typeof Badge>;

export const Accent: Story = {
  args: {
    variant: "accent",
    children: "Accent",
  },
};

export const Success: Story = {
  args: {
    variant: "success",
    children: "Active",
  },
};

export const Warning: Story = {
  args: {
    variant: "warning",
    children: "Pending",
  },
};

export const Danger: Story = {
  args: {
    variant: "danger",
    children: "Failed",
  },
};

export const Info: Story = {
  args: {
    variant: "info",
    children: "Info",
  },
};

export const Neutral: Story = {
  args: {
    variant: "neutral",
    children: "Draft",
  },
};

export const Outline: Story = {
  args: {
    variant: "outline",
    children: "v0.4.2",
  },
};

export const WithDot: Story = {
  name: "With Dot Indicator",
  render: () => (
    <div className="flex items-center gap-3">
      <Badge variant="success">
        <BadgeDot />
        Online
      </Badge>
      <Badge variant="warning">
        <BadgeDot />
        Pending
      </Badge>
      <Badge variant="danger">
        <BadgeDot />
        Failed
      </Badge>
    </div>
  ),
};

export const AllVariants: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-2">
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
