import type { Meta, StoryObj } from "@storybook/react"
import React from "react"

import { Spinner } from "@/components/ui/spinner"

const meta: Meta<typeof Spinner> = {
  title: "Primitives/Spinner",
  component: Spinner,
  parameters: {
    layout: "centered",
  },
  argTypes: {
    size: {
      control: "select",
      options: ["sm", "md", "lg"],
    },
    variant: {
      control: "select",
      options: ["default", "accent"],
    },
  },
}

export default meta

type Story = StoryObj<typeof Spinner>

export const Default: Story = {
  args: {
    size: "md",
    variant: "default",
  },
}

export const Small: Story = {
  name: "Size: sm",
  args: {
    size: "sm",
    variant: "default",
  },
}

export const Medium: Story = {
  name: "Size: md",
  args: {
    size: "md",
    variant: "default",
  },
}

export const Large: Story = {
  name: "Size: lg",
  args: {
    size: "lg",
    variant: "default",
  },
}

export const Accent: Story = {
  name: "Variant: accent",
  args: {
    size: "md",
    variant: "accent",
  },
}

export const AllSizes: Story = {
  name: "All Sizes",
  render: () => (
    <div className="flex items-center gap-6">
      <Spinner size="sm" variant="default" />
      <Spinner size="md" variant="default" />
      <Spinner size="lg" variant="default" />
    </div>
  ),
}

export const AllVariants: Story = {
  name: "All Variants",
  render: () => (
    <div className="flex items-center gap-6">
      <Spinner size="md" variant="default" />
      <Spinner size="md" variant="accent" />
    </div>
  ),
}
