import type { Meta, StoryObj } from "@storybook/react"
import React from "react"

import { KeyValue, KeyValueList } from "../components/ui/key-value"

const meta: Meta<typeof KeyValue> = {
  title: "Data Display/KeyValue",
  component: KeyValue,
  parameters: { layout: "centered" },
  argTypes: {
    label: {
      control: "text",
      description: "Key column label",
    },
    value: {
      control: "text",
      description: "Value column content",
    },
    mono: {
      control: "boolean",
      description: "Render value in monospace font (default: true per DS spec)",
    },
  },
}
export default meta

type Story = StoryObj<typeof KeyValue>

export const Default: Story = {
  name: "Default (controls)",
  args: {
    label: "Run ID",
    value: "run_8f3k2m",
    mono: true,
  },
}

export const List: Story = {
  name: "List",
  render: () => (
    <div style={{ width: 320 }}>
      <KeyValueList
        items={[
          { label: "Run ID", value: "run_8f3k2m" },
          { label: "Duration", value: "34s" },
          { label: "Total Tokens", value: "3,891" },
          { label: "Cost", value: "$0.0142" },
        ]}
      />
    </div>
  ),
}

export const MonoValues: Story = {
  name: "Mono Values",
  render: () => (
    <div style={{ width: 320 }}>
      <KeyValueList
        items={[
          { label: "Commit", value: "a1b2c3d", mono: true },
          { label: "Branch", value: "main", mono: true },
          { label: "Model", value: "gpt-4o", mono: true },
          { label: "Status", value: "completed", mono: false },
        ]}
      />
    </div>
  ),
}
