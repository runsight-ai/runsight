import type { Meta, StoryObj } from "@storybook/react"
import React from "react"

import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from "@/components/ui/input-group"

const meta = {
  title: "Forms/InputGroup",
  component: InputGroup,
  parameters: { layout: "centered" },
  argTypes: {
    className: {
      control: false,
      description: "Additional CSS classes for the group wrapper",
    },
  },
  decorators: [
    (Story) => (
      <div style={{ width: "288px" }}>
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof InputGroup>

export default meta

type Story = StoryObj<typeof meta>

export const WithPrefix: Story = {
  name: "With Prefix",
  render: () => (
    <InputGroup>
      <InputGroupAddon align="inline-start">$</InputGroupAddon>
      <InputGroupInput type="number" placeholder="0.00" />
    </InputGroup>
  ),
}

export const WithSuffix: Story = {
  name: "With Suffix",
  render: () => (
    <InputGroup>
      <InputGroupInput type="number" placeholder="Tokens per second" />
      <InputGroupAddon align="inline-end">tok/s</InputGroupAddon>
    </InputGroup>
  ),
}

export const WithBoth: Story = {
  name: "With Prefix and Suffix",
  render: () => (
    <InputGroup>
      <InputGroupAddon align="inline-start">https://</InputGroupAddon>
      <InputGroupInput type="text" placeholder="api.example.com" />
      <InputGroupAddon align="inline-end">/v1</InputGroupAddon>
    </InputGroup>
  ),
}

export const Disabled: Story = {
  render: () => (
    <InputGroup>
      <InputGroupAddon align="inline-start">@</InputGroupAddon>
      <InputGroupInput type="text" placeholder="username" disabled />
    </InputGroup>
  ),
}
