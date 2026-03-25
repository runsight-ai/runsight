import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { Skeleton } from "@/components/ui/skeleton";

const meta: Meta<typeof Skeleton> = {
  title: "Primitives/Skeleton",
  component: Skeleton,
  parameters: { layout: "centered" },
  argTypes: {
    variant: {
      control: { type: "select" },
      options: ["text", "text-sm", "heading", "avatar", "button"],
      description: "Skeleton shape variant",
    },
  },
};
export default meta;

type Story = StoryObj<typeof Skeleton>;

export const Default: Story = {
  name: "Default (controls)",
  args: {
    variant: "text",
  },
};

export const AllVariants: Story = {
  name: "All Variants",
  render: () => (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-4)",
        padding: "var(--space-6)",
        width: "320px",
        background: "var(--surface-primary)",
        borderRadius: "var(--radius-lg)",
      }}
    >
      <Skeleton variant="heading" />
      <Skeleton variant="text" />
      <Skeleton variant="text" />
      <Skeleton variant="text-sm" />
      <Skeleton variant="avatar" />
      <Skeleton variant="button" />
    </div>
  ),
};

export const LoadingCard: Story = {
  name: "Loading Card (composition)",
  render: () => (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-4)",
        padding: "var(--space-6)",
        width: "320px",
        background: "var(--surface-primary)",
        borderRadius: "var(--radius-lg)",
      }}
    >
      <Skeleton variant="heading" />
      <Skeleton variant="text" />
      <Skeleton variant="text" />
      <Skeleton variant="text-sm" />
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", marginTop: "var(--space-2)" }}>
        <Skeleton variant="avatar" />
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
          <Skeleton variant="text" />
          <Skeleton variant="text-sm" />
        </div>
      </div>
      <Skeleton variant="button" />
    </div>
  ),
};
