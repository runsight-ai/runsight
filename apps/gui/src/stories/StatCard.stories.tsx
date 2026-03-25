import type { Meta, StoryObj } from "@storybook/react"
import React from "react"

import { StatCard } from "@/components/ui/stat-card"

const meta: Meta<typeof StatCard> = {
  title: "Data Display/StatCard",
  component: StatCard,
  parameters: {
    layout: "padded",
  },
  argTypes: {
    variant: {
      control: "select",
      options: ["default", "accent", "success", "danger"],
    },
  },
}

export default meta

type Story = StoryObj<typeof StatCard>

// ---------------------------------------------------------------------------
// Default — basic stat display
// ---------------------------------------------------------------------------

export const Default: Story = {
  args: {
    label: "Active Workflows",
    value: "12",
    variant: "default",
  },
}

// ---------------------------------------------------------------------------
// WithDelta — stat with a delta/trend badge showing positive change
// ---------------------------------------------------------------------------

export const WithDelta: Story = {
  name: "With Delta Badge",
  args: {
    label: "Completed Runs",
    value: "4,820",
    delta: "↑ +18% this week",
    variant: "accent",
  },
}

// ---------------------------------------------------------------------------
// TrendDown — stat with negative delta/trend
// ---------------------------------------------------------------------------

export const TrendDown: Story = {
  name: "Trend Down",
  args: {
    label: "Error Rate",
    value: "2.4%",
    delta: "↓ -0.3% vs last week",
    variant: "danger",
  },
}

// ---------------------------------------------------------------------------
// AllVariants — all stripe color variants side by side
// ---------------------------------------------------------------------------

export const AllVariants: Story = {
  name: "All Variants",
  render: () => (
    <div className="flex flex-wrap gap-4">
      <StatCard label="Default" value="42" variant="default" />
      <StatCard label="Accent" value="128" variant="accent" delta="+12" />
      <StatCard label="Success" value="99.8%" variant="success" delta="↑ +0.2%" />
      <StatCard label="Danger" value="4" variant="danger" delta="↓ -2" />
    </div>
  ),
}

// ---------------------------------------------------------------------------
// TrendVariants — demonstrates delta/change/trend prop patterns
// ---------------------------------------------------------------------------

export const TrendVariants: Story = {
  name: "Trend Variants",
  render: () => (
    <div className="flex flex-wrap gap-4">
      <StatCard
        label="Total Runs"
        value="1,204"
        delta="↑ 204 this week"
        variant="accent"
      />
      <StatCard
        label="Avg Duration"
        value="34s"
        delta="↓ -8s improvement"
        variant="success"
      />
      <StatCard
        label="Failed Runs"
        value="7"
        delta="↑ +3 vs yesterday"
        variant="danger"
      />
    </div>
  ),
}
