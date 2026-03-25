import type { Meta, StoryObj } from "@storybook/react"
import React from "react"

import { StatusDot } from "@/components/ui/status-dot"

const meta: Meta<typeof StatusDot> = {
  title: "Primitives/StatusDot",
  component: StatusDot,
  parameters: {
    layout: "centered",
  },
  argTypes: {
    variant: {
      control: "select",
      options: ["neutral", "active", "success", "warning", "danger"],
    },
    animate: {
      control: "select",
      options: ["none", "pulse", "spin"],
    },
  },
}

export default meta

type Story = StoryObj<typeof StatusDot>

export const Neutral: Story = {
  name: "Variant: neutral",
  args: {
    variant: "neutral",
    animate: "none",
  },
}

export const Active: Story = {
  name: "Variant: active",
  args: {
    variant: "active",
    animate: "none",
  },
}

export const Success: Story = {
  name: "Variant: success",
  args: {
    variant: "success",
    animate: "none",
  },
}

export const Warning: Story = {
  name: "Variant: warning",
  args: {
    variant: "warning",
    animate: "none",
  },
}

export const Danger: Story = {
  name: "Variant: danger",
  args: {
    variant: "danger",
    animate: "none",
  },
}

export const Pulse: Story = {
  name: "Animation: pulse",
  args: {
    variant: "active",
    animate: "pulse",
  },
}

export const Spin: Story = {
  name: "Animation: spin",
  args: {
    variant: "warning",
    animate: "spin",
  },
}

export const AllVariants: Story = {
  name: "All Variants",
  render: () => (
    <div className="flex items-center gap-4 p-4">
      <StatusDot variant="neutral" animate="none" />
      <StatusDot variant="active" animate="none" />
      <StatusDot variant="success" animate="none" />
      <StatusDot variant="warning" animate="none" />
      <StatusDot variant="danger" animate="none" />
    </div>
  ),
}

export const AllAnimations: Story = {
  name: "All Animations (pulse + spin)",
  render: () => (
    <div className="flex items-center gap-6 p-4">
      <StatusDot variant="active" animate="pulse" />
      <StatusDot variant="warning" animate="spin" />
      <StatusDot variant="success" animate="none" />
    </div>
  ),
}
