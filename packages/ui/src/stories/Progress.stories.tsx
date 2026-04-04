import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { Progress } from "../components/ui/progress";

const meta: Meta<typeof Progress> = {
  title: "Primitives/Progress",
  component: Progress,
  parameters: { layout: "centered" },
  argTypes: {
    variant: {
      control: { type: "select" },
      options: ["default", "md", "success", "danger", "indeterminate"],
      description: "Visual variant of the progress bar",
    },
    value: {
      control: { type: "range", min: 0, max: 100, step: 1 },
      description: "Progress value (0–100), ignored when variant is indeterminate",
    },
  },
};
export default meta;

type Story = StoryObj<typeof Progress>;

export const Default: Story = {
  name: "Default (controls)",
  args: {
    variant: "default",
    value: 60,
  },
  decorators: [
    (Story) => (
      <div style={{ width: "280px" }}>
        <Story />
      </div>
    ),
  ],
};

export const Variants: Story = {
  name: "All Variants",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)", padding: "var(--space-4)", width: "320px" }}>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
        <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>Default (60%)</span>
        <Progress variant="default" value={60} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
        <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>md (40%)</span>
        <Progress variant="md" value={40} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
        <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>Success (100%)</span>
        <Progress variant="success" value={100} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
        <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>Danger (25%)</span>
        <Progress variant="danger" value={25} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
        <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>Indeterminate</span>
        <Progress variant="indeterminate" />
      </div>
    </div>
  ),
};

export const Indeterminate: Story = {
  name: "Indeterminate",
  render: () => (
    <div style={{ width: "280px" }}>
      <Progress variant="indeterminate" />
    </div>
  ),
};
