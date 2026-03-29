import type { Meta, StoryObj } from "@storybook/react"
import React from "react"

import { Slider } from "../components/ui/slider"

const meta = {
  title: "Forms/Slider",
  component: Slider,
  parameters: { layout: "centered" },
  argTypes: {
    min: {
      control: { type: "number" },
      description: "Minimum value",
    },
    max: {
      control: { type: "number" },
      description: "Maximum value",
    },
    step: {
      control: { type: "number" },
      description: "Step increment",
    },
    defaultValue: {
      control: { type: "number" },
      description: "Initial value (uncontrolled)",
    },
    disabled: {
      control: "boolean",
      description: "Disables the slider",
    },
  },
  args: {
    min: 0,
    max: 100,
    step: 1,
    defaultValue: 50,
    disabled: false,
  },
  decorators: [
    (Story) => (
      <div style={{ width: "280px" }}>
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof Slider>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    min: 0,
    max: 100,
    step: 1,
    defaultValue: 50,
  },
}

export const Range: Story = {
  name: "Token Budget (256–8192)",
  render: function RangeStory() {
    const [value, setValue] = React.useState(2048)
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            fontSize: "var(--font-size-sm)",
            color: "var(--text-primary)",
          }}
        >
          <span>Max tokens</span>
          <span style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
            {value.toLocaleString()}
          </span>
        </div>
        <Slider
          min={256}
          max={8192}
          step={256}
          value={value}
          onChange={(e) => setValue(Number((e.target as HTMLInputElement).value))}
          aria-label="Max tokens"
        />
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            fontSize: "var(--font-size-xs)",
            color: "var(--text-muted)",
            fontFamily: "var(--font-mono)",
          }}
        >
          <span>256</span>
          <span>8,192</span>
        </div>
      </div>
    )
  },
}

export const Disabled: Story = {
  args: {
    defaultValue: 60,
    disabled: true,
  },
}
