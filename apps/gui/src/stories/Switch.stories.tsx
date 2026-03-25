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
  args: {
    defaultChecked: false,
  },
}

export const Disabled: Story = {
  args: {
    defaultChecked: false,
    disabled: true,
  },
}

export const WithLabel: Story = {
  render: (args) => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <label style={{ display: "inline-flex", alignItems: "center", gap: "var(--space-2)", cursor: "pointer", userSelect: "none" }}>
        <Switch {...args} defaultChecked={false} />
        <span style={{ fontSize: "var(--font-size-md)", color: "var(--text-primary)" }}>Auto-retry on failure</span>
      </label>
      <label style={{ display: "inline-flex", alignItems: "center", gap: "var(--space-2)", cursor: "pointer", userSelect: "none" }}>
        <Switch {...args} defaultChecked={true} />
        <span style={{ fontSize: "var(--font-size-md)", color: "var(--text-primary)" }}>Stream output</span>
      </label>
      <label style={{ display: "inline-flex", alignItems: "center", gap: "var(--space-2)", cursor: "pointer", userSelect: "none" }}>
        <Switch {...args} disabled />
        <span style={{ fontSize: "var(--font-size-md)", color: "var(--text-primary)" }}>Disabled</span>
      </label>
    </div>
  ),
}
