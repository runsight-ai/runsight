import type { Meta, StoryObj } from "@storybook/react"
import React from "react"

import { Radio, RadioGroup } from "../components/ui/radio"

const meta = {
  title: "Forms/Radio",
  component: RadioGroup,
  parameters: { layout: "centered" },
  argTypes: {
    orientation: {
      control: "select",
      options: ["vertical", "horizontal"],
      description: "Layout direction of the radio group",
    },
  },
  args: {
    orientation: "vertical",
  },
} satisfies Meta<typeof RadioGroup>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    orientation: "vertical",
  },
  render: (args) => (
    <RadioGroup {...args}>
      <Radio label="claude-sonnet-4-6" name="model-default" value="sonnet" defaultChecked />
      <Radio label="gpt-4o" name="model-default" value="gpt4o" />
      <Radio label="gemini-2.0" name="model-default" value="gemini" />
    </RadioGroup>
  ),
}

export const Horizontal: Story = {
  args: {
    orientation: "horizontal",
  },
  render: (args) => (
    <RadioGroup {...args}>
      <Radio label="Small" name="size-h" value="sm" />
      <Radio label="Medium" name="size-h" value="md" defaultChecked />
      <Radio label="Large" name="size-h" value="lg" />
    </RadioGroup>
  ),
}

export const Disabled: Story = {
  args: {
    orientation: "vertical",
  },
  render: (args) => (
    <RadioGroup {...args}>
      <Radio label="Option A (disabled)" name="disabled-group" value="a" disabled />
      <Radio label="Option B (disabled, checked)" name="disabled-group" value="b" disabled defaultChecked />
    </RadioGroup>
  ),
}
