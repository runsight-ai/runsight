import type { Meta, StoryObj } from "@storybook/react"
import React from "react"

import { Divider } from "../components/ui/divider"

const meta: Meta<typeof Divider> = {
  title: "Primitives/Divider",
  component: Divider,
  parameters: { layout: "centered" },
  argTypes: {
    orientation: {
      control: { type: "select" },
      options: ["horizontal", "vertical"],
      description: "Divider orientation",
    },
  },
}
export default meta

type Story = StoryObj<typeof Divider>

export const Default: Story = {
  name: "Default (controls)",
  args: {
    orientation: "horizontal",
  },
  render: (args) => (
    <div style={{ width: 300 }}>
      {args.orientation === "vertical" ? (
        <div style={{ display: "flex", alignItems: "stretch", height: 40, gap: "var(--space-4)" }}>
          <span style={{ color: "var(--text-secondary)" }}>Left</span>
          <Divider {...args} />
          <span style={{ color: "var(--text-secondary)" }}>Right</span>
        </div>
      ) : (
        <Divider {...args} />
      )}
    </div>
  ),
}

export const Horizontal: Story = {
  name: "Horizontal",
  render: () => (
    <div style={{ width: 320 }}>
      <p style={{ color: "var(--text-secondary)", marginBottom: "var(--space-3)" }}>Content above</p>
      <Divider orientation="horizontal" />
      <p style={{ color: "var(--text-secondary)", marginTop: "var(--space-3)" }}>Content below</p>
    </div>
  ),
}

export const Vertical: Story = {
  name: "Vertical",
  render: () => (
    <div style={{ display: "flex", alignItems: "stretch", height: 40, gap: "var(--space-4)" }}>
      <span style={{ color: "var(--text-secondary)" }}>Left</span>
      <Divider orientation="vertical" />
      <span style={{ color: "var(--text-secondary)" }}>Right</span>
    </div>
  ),
}
