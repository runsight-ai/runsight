import type { Meta, StoryObj } from "@storybook/react"
import React from "react"

import { Checkbox } from "@/components/ui/checkbox"

const meta = {
  title: "Forms/Checkbox",
  component: Checkbox,
  parameters: { layout: "centered" },
  argTypes: {
    label: {
      control: "text",
      description: "Label text rendered next to the checkbox",
    },
    indeterminate: {
      control: "boolean",
      description: "Sets the indeterminate state on the underlying input",
    },
    disabled: {
      control: "boolean",
      description: "Disables the checkbox",
    },
    defaultChecked: {
      control: "boolean",
      description: "Initial checked state (uncontrolled)",
    },
  },
  args: {
    label: "Accept terms",
    indeterminate: false,
    disabled: false,
    defaultChecked: false,
  },
} satisfies Meta<typeof Checkbox>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    label: "Accept terms",
  },
}

export const Checked: Story = {
  args: {
    label: "Checked",
    defaultChecked: true,
  },
}

export const Indeterminate: Story = {
  args: {
    label: "Indeterminate",
    indeterminate: true,
  },
}

export const Disabled: Story = {
  args: {
    label: "Disabled",
    disabled: true,
  },
}

export const Group: Story = {
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <Checkbox label="Unchecked" />
      <Checkbox label="Checked" defaultChecked />
      <Checkbox label="Indeterminate" indeterminate />
      <Checkbox label="Disabled" disabled />
    </div>
  ),
}
