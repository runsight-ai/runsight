import type { Meta, StoryObj } from "@storybook/react"
import React from "react"

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

const meta = {
  title: "Forms/Select",
  component: Select,
  parameters: { layout: "centered" },
  argTypes: {
    disabled: {
      control: "boolean",
      description: "Disables the select trigger",
    },
    defaultValue: {
      control: "text",
      description: "Default selected value (uncontrolled)",
    },
  },
  args: {
    disabled: false,
  },
  decorators: [
    (Story) => (
      <div style={{ width: "220px" }}>
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof Select>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    disabled: false,
  },
  render: (args) => (
    <Select {...args}>
      <SelectTrigger>
        <SelectValue placeholder="Select a model" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="claude-3-5-sonnet">Claude 3.5 Sonnet</SelectItem>
        <SelectItem value="claude-3-opus">Claude 3 Opus</SelectItem>
        <SelectItem value="claude-3-haiku">Claude 3 Haiku</SelectItem>
        <SelectItem value="gpt-4o">GPT-4o</SelectItem>
        <SelectItem value="gpt-4-turbo">GPT-4 Turbo</SelectItem>
      </SelectContent>
    </Select>
  ),
}

export const WithLabel: Story = {
  render: (args) => (
    <div className="field">
      <label className="field__label">Model</label>
      <Select {...args}>
        <SelectTrigger>
          <SelectValue placeholder="Select model…" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="claude-3-5-sonnet">Claude 3.5 Sonnet</SelectItem>
          <SelectItem value="claude-3-opus">Claude 3 Opus</SelectItem>
          <SelectItem value="gpt-4o">GPT-4o</SelectItem>
        </SelectContent>
      </Select>
    </div>
  ),
}

export const Disabled: Story = {
  args: {
    disabled: true,
  },
  render: (args) => (
    <Select {...args}>
      <SelectTrigger>
        <SelectValue placeholder="Disabled select" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="a">Option A</SelectItem>
      </SelectContent>
    </Select>
  ),
}

export const MultipleOptions: Story = {
  name: "Multiple Options",
  render: (args) => (
    <Select {...args} defaultValue="gemini-2-0">
      <SelectTrigger>
        <SelectValue placeholder="Select a provider" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="claude-3-5-sonnet">Claude 3.5 Sonnet</SelectItem>
        <SelectItem value="claude-3-opus">Claude 3 Opus</SelectItem>
        <SelectItem value="claude-3-haiku">Claude 3 Haiku</SelectItem>
        <SelectItem value="gpt-4o">GPT-4o</SelectItem>
        <SelectItem value="gpt-4-turbo">GPT-4 Turbo</SelectItem>
        <SelectItem value="gemini-2-0">Gemini 2.0</SelectItem>
        <SelectItem value="gemini-1-5-pro">Gemini 1.5 Pro</SelectItem>
      </SelectContent>
    </Select>
  ),
}
