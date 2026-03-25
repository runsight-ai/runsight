import type { Meta, StoryObj } from "@storybook/react"
import React from "react"

import { Skeleton } from "@/components/ui/skeleton"

const meta: Meta<typeof Skeleton> = {
  title: "Primitives/Skeleton",
  component: Skeleton,
  parameters: {
    layout: "centered",
  },
  argTypes: {
    variant: {
      control: "select",
      options: ["text", "text-sm", "heading", "avatar", "button"],
    },
  },
}

export default meta

type Story = StoryObj<typeof Skeleton>

export const Text: Story = {
  name: "Variant: text",
  args: {
    variant: "text",
  },
}

export const TextSm: Story = {
  name: "Variant: text-sm",
  args: {
    variant: "text-sm",
  },
}

export const Heading: Story = {
  name: "Variant: heading",
  args: {
    variant: "heading",
  },
}

export const Avatar: Story = {
  name: "Variant: avatar",
  args: {
    variant: "avatar",
  },
}

export const Button: Story = {
  name: "Variant: button",
  args: {
    variant: "button",
  },
}

export const AllVariants: Story = {
  name: "All Variants",
  render: () => (
    <div className="flex w-72 flex-col gap-4 p-4">
      <Skeleton variant="heading" />
      <Skeleton variant="text" />
      <Skeleton variant="text-sm" />
      <div className="flex items-center gap-3">
        <Skeleton variant="avatar" />
        <div className="flex flex-1 flex-col gap-2">
          <Skeleton variant="text" />
          <Skeleton variant="text-sm" />
        </div>
      </div>
      <Skeleton variant="button" />
    </div>
  ),
}
