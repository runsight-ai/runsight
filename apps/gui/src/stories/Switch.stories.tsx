import type { Meta, StoryObj } from "@storybook/react"
import React from "react"

import { Switch } from "@/components/ui/switch"

const meta = {
  title: "Forms/Switch",
  component: Switch,
  parameters: { layout: "centered" },
  argTypes: {
    checked: {
      control: "boolean",
      description: "Controlled checked state",
    },
    defaultChecked: {
      control: "boolean",
      description: "Initial checked state (uncontrolled)",
    },
    disabled: {
      control: "boolean",
      description: "Disables the switch",
    },
    label: {
      control: "text",
      description: "Optional label text rendered as .switch__label",
    },
    onCheckedChange: {
      action: "onCheckedChange",
      description: "Callback fired when the checked state changes",
    },
  },
  args: {
    defaultChecked: false,
    disabled: false,
  },
} satisfies Meta<typeof Switch>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  name: "Default",
  args: {
    defaultChecked: false,
  },
}

export const Checked: Story = {
  name: "Checked",
  args: {
    defaultChecked: true,
  },
}

export const WithLabel: Story = {
  name: "With Label",
  args: {
    defaultChecked: true,
    label: "Stream output",
  },
}

export const Disabled: Story = {
  name: "Disabled",
  args: {
    defaultChecked: false,
    disabled: true,
  },
}

export const DisabledChecked: Story = {
  name: "Disabled Checked",
  args: {
    defaultChecked: true,
    disabled: true,
    label: "Auto-retry on failure",
  },
}

export const Showcase: Story = {
  name: "Showcase — all states",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Switch defaultChecked={false} label="Auto-retry on failure" />
      <Switch defaultChecked={true} label="Stream output" />
      <Switch defaultChecked={false} disabled label="Disabled (off)" />
      <Switch defaultChecked={true} disabled label="Disabled (on)" />
    </div>
  ),
}
