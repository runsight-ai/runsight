import type { Meta, StoryObj } from "@storybook/react"
import React from "react"

import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

const meta: Meta<typeof Card> = {
  title: "Data Display/Card",
  component: Card,
  parameters: {
    layout: "padded",
  },
}

export default meta

type Story = StoryObj<typeof Card>

// ---------------------------------------------------------------------------
// Default — basic card
// ---------------------------------------------------------------------------

export const Default: Story = {
  render: () => (
    <Card className="max-w-sm">
      <CardContent>
        <p>A simple card with content and no header.</p>
      </CardContent>
    </Card>
  ),
}

// ---------------------------------------------------------------------------
// WithHeader — card with CardHeader and CardTitle
// ---------------------------------------------------------------------------

export const WithHeader: Story = {
  name: "With Header",
  render: () => (
    <Card className="max-w-sm">
      <CardHeader>
        <CardTitle>Active Workflows</CardTitle>
        <CardDescription>Workflows currently running in your workspace.</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-font-size-sm text-secondary">12 workflows are currently active.</p>
      </CardContent>
    </Card>
  ),
}

// ---------------------------------------------------------------------------
// WithHeaderAndAction — card with header, action button, and footer
// ---------------------------------------------------------------------------

export const WithHeaderAndAction: Story = {
  name: "With Header and Action",
  render: () => (
    <Card className="max-w-sm">
      <CardHeader>
        <CardTitle>Workflow Overview</CardTitle>
        <CardDescription>Summary of your most recent runs.</CardDescription>
        <CardAction>
          <button
            type="button"
            className="text-font-size-xs text-secondary hover:text-primary"
          >
            View all
          </button>
        </CardAction>
      </CardHeader>
      <CardContent>
        <p className="text-font-size-sm text-secondary">
          3 completed, 1 running, 0 failed.
        </p>
      </CardContent>
      <CardFooter>
        <span className="text-font-size-xs text-secondary">Updated 2 min ago</span>
      </CardFooter>
    </Card>
  ),
}

// ---------------------------------------------------------------------------
// SmallSize — compact card variant
// ---------------------------------------------------------------------------

export const SmallSize: Story = {
  name: "Small Size",
  render: () => (
    <Card size="sm" className="max-w-xs">
      <CardHeader>
        <CardTitle>Run Count</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-font-size-sm">42 runs today</p>
      </CardContent>
    </Card>
  ),
}
