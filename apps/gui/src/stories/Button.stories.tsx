import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { Button } from "@/components/ui/button";

const meta: Meta<typeof Button> = {
  title: "Primitives/Button",
  component: Button,
  parameters: {
    layout: "centered",
  },
  argTypes: {
    variant: {
      control: "select",
      options: ["primary", "secondary", "ghost", "danger", "icon-only"],
    },
    size: {
      control: "select",
      options: ["xs", "sm", "md", "lg"],
    },
    loading: { control: "boolean" },
    disabled: { control: "boolean" },
  },
};

export default meta;

type Story = StoryObj<typeof Button>;

export const Primary: Story = {
  args: {
    variant: "primary",
    size: "sm",
    children: "Save Workflow",
  },
};

export const Secondary: Story = {
  args: {
    variant: "secondary",
    size: "sm",
    children: "Cancel",
  },
};

export const Ghost: Story = {
  args: {
    variant: "ghost",
    size: "sm",
    children: "Reset",
  },
};

export const Danger: Story = {
  args: {
    variant: "danger",
    size: "sm",
    children: "Delete Workflow",
  },
};

export const IconOnly: Story = {
  name: "Icon Only",
  args: {
    variant: "icon-only",
    size: "sm",
    "aria-label": "Settings",
    children: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        className="size-4"
      >
        <path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
};

export const Loading: Story = {
  args: {
    variant: "primary",
    size: "sm",
    loading: true,
    children: "Saving...",
  },
};

export const Sizes: Story = {
  render: () => (
    <div className="flex items-center gap-3">
      <Button variant="primary" size="xs">XS</Button>
      <Button variant="primary" size="sm">SM</Button>
      <Button variant="primary" size="md">MD</Button>
      <Button variant="primary" size="lg">LG</Button>
    </div>
  ),
};

export const AllVariants: Story = {
  render: () => (
    <div className="flex items-center gap-3">
      <Button variant="primary">Primary</Button>
      <Button variant="secondary">Secondary</Button>
      <Button variant="ghost">Ghost</Button>
      <Button variant="danger">Danger</Button>
    </div>
  ),
};

export const Disabled: Story = {
  args: {
    variant: "primary",
    size: "sm",
    disabled: true,
    children: "Disabled",
  },
};
