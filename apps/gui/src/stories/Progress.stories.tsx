import type { Meta, StoryObj } from "@storybook/react"
import React from "react"

import { Progress } from "@/components/ui/progress"

const meta: Meta<typeof Progress> = {
  title: "Primitives/Progress",
  component: Progress,
  parameters: {
    layout: "centered",
  },
  argTypes: {
    variant: {
      control: "select",
      options: ["default", "md", "success", "danger", "indeterminate"],
    },
    value: {
      control: { type: "range", min: 0, max: 100, step: 1 },
    },
  },
}

export default meta

type Story = StoryObj<typeof Progress>

export const Default: Story = {
  args: {
    variant: "default",
    value: 60,
  },
}

export const Medium: Story = {
  name: "Variant: md",
  args: {
    variant: "md",
    value: 40,
  },
}

export const Success: Story = {
  name: "Variant: success",
  args: {
    variant: "success",
    value: 100,
  },
}

export const Danger: Story = {
  name: "Variant: danger",
  args: {
    variant: "danger",
    value: 25,
  },
}

export const Indeterminate: Story = {
  name: "Variant: indeterminate",
  args: {
    variant: "indeterminate",
    value: 0,
  },
}

export const AllVariants: Story = {
  name: "All Variants",
  render: () => (
    <div className="flex w-80 flex-col gap-4 p-4">
      <div className="flex flex-col gap-1">
        <span className="text-xs text-muted">Default (60%)</span>
        <Progress variant="default" value={60} />
      </div>
      <div className="flex flex-col gap-1">
        <span className="text-xs text-muted">Success (100%)</span>
        <Progress variant="success" value={100} />
      </div>
      <div className="flex flex-col gap-1">
        <span className="text-xs text-muted">Danger (25%)</span>
        <Progress variant="danger" value={25} />
      </div>
      <div className="flex flex-col gap-1">
        <span className="text-xs text-muted">Indeterminate</span>
        <Progress variant="indeterminate" />
      </div>
    </div>
  ),
}
