import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { Spinner } from "@/components/ui/spinner";

const meta: Meta<typeof Spinner> = {
  title: "Primitives/Spinner",
  component: Spinner,
  parameters: { layout: "centered" },
  argTypes: {
    size: {
      control: { type: "select" },
      options: ["sm", "md", "lg"],
      description: "Size of the spinner",
    },
    variant: {
      control: { type: "select" },
      options: ["default", "accent"],
      description: "Visual variant of the spinner",
    },
  },
};
export default meta;

type Story = StoryObj<typeof Spinner>;

export const Default: Story = {
  name: "Default (controls)",
  args: {
    size: "md",
    variant: "default",
  },
};

export const AllSizes: Story = {
  name: "All Sizes",
  render: () => (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-6)" }}>
      <Spinner size="sm" />
      <Spinner size="md" />
      <Spinner size="lg" />
    </div>
  ),
};

export const AllVariants: Story = {
  name: "All Variants",
  render: () => (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-6)" }}>
      <Spinner size="md" variant="default" />
      <Spinner size="md" variant="accent" />
    </div>
  ),
};
