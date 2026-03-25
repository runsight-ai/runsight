import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { StatCard } from "@/components/ui/stat-card";

const meta: Meta<typeof StatCard> = {
  title: "Data Display/StatCard",
  component: StatCard,
  parameters: { layout: "padded" },
  argTypes: {
    label: {
      control: { type: "text" },
      description: "Metric label — displayed uppercase in font-size-xs",
    },
    value: {
      control: { type: "text" },
      description: "Metric value — displayed in font-mono font-size-2xl",
    },
    variant: {
      control: { type: "select" },
      options: ["default", "accent", "success", "danger"],
      description: "Visual variant controls the top category stripe color",
    },
    delta: {
      control: { type: "text" },
      description: "Optional delta/change/trend indicator (e.g. +12%, ↑ +18, -3%)",
    },
    icon: {
      control: false,
      description: "Optional icon displayed alongside the value (ReactNode)",
    },
  },
};
export default meta;

type Story = StoryObj<typeof StatCard>;

export const Default: Story = {
  name: "Default (controls)",
  args: {
    label: "Active Workflows",
    value: "12",
    variant: "default",
    delta: undefined,
  },
  render: (args) => (
    <div style={{ width: "200px" }}>
      <StatCard {...args} />
    </div>
  ),
};

export const AllVariants: Story = {
  name: "All Variants",
  render: () => (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-4)" }}>
      <StatCard label="Default" value="42" style={{ width: "180px" }} />
      <StatCard label="Accent" value="128" variant="accent" delta="+12" style={{ width: "180px" }} />
      <StatCard label="Success" value="99.8%" variant="success" delta="↑ +0.2%" style={{ width: "180px" }} />
      <StatCard label="Danger" value="4" variant="danger" delta="↓ -2" style={{ width: "180px" }} />
    </div>
  ),
};

export const WithDelta: Story = {
  name: "With Delta",
  render: () => (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-4)" }}>
      <StatCard
        label="Completed Runs"
        value="4,820"
        variant="accent"
        delta="↑ +18% this week"
        style={{ width: "200px" }}
      />
      <StatCard
        label="Error Rate"
        value="2.4%"
        variant="danger"
        delta="↓ -0.3% vs last week"
        style={{ width: "200px" }}
      />
    </div>
  ),
};

export const TrendUp: Story = {
  name: "Trend Up (.stat-card__trend--up)",
  render: () => (
    <StatCard
      label="Completed Runs"
      value="4,820"
      variant="success"
      delta="↑ +18% this week"
      style={{ width: "220px" }}
    />
  ),
};

export const TrendDown: Story = {
  name: "Trend Down (.stat-card__trend--down)",
  render: () => (
    <StatCard
      label="Error Rate"
      value="2.4%"
      variant="danger"
      delta="↓ -0.3% vs last week"
      style={{ width: "220px" }}
    />
  ),
};
