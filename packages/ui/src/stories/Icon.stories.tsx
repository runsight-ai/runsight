import type { Meta, StoryObj } from "@storybook/react"
import React from "react"

import { Icon } from "../components/ui/icon"

// Sample SVG path used across all icon stories
const PlusCircleSvg = () => (
  <svg viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="10" />
    <path d="M12 8v8M8 12h8" />
  </svg>
)

const meta: Meta<typeof Icon> = {
  title: "Primitives/Icon",
  component: Icon,
  parameters: { layout: "centered" },
  argTypes: {
    size: {
      control: { type: "select" },
      options: ["xs", "sm", "md", "lg", "xl"],
      description: "Icon size variant",
    },
    children: {
      control: false,
      description: "SVG content",
    },
  },
}
export default meta

type Story = StoryObj<typeof Icon>

export const Default: Story = {
  name: "Default (controls)",
  args: {
    size: "md",
  },
  render: (args) => (
    <Icon {...args}>
      <PlusCircleSvg />
    </Icon>
  ),
}

export const AllSizes: Story = {
  name: "All Sizes",
  render: () => (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)" }}>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--space-1)" }}>
        <Icon size="xs"><PlusCircleSvg /></Icon>
        <span style={{ fontSize: "var(--font-size-2xs)", color: "var(--text-muted)" }}>xs 12px</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--space-1)" }}>
        <Icon size="sm"><PlusCircleSvg /></Icon>
        <span style={{ fontSize: "var(--font-size-2xs)", color: "var(--text-muted)" }}>sm 14px</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--space-1)" }}>
        <Icon size="md"><PlusCircleSvg /></Icon>
        <span style={{ fontSize: "var(--font-size-2xs)", color: "var(--text-muted)" }}>md 16px</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--space-1)" }}>
        <Icon size="lg"><PlusCircleSvg /></Icon>
        <span style={{ fontSize: "var(--font-size-2xs)", color: "var(--text-muted)" }}>lg 20px</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--space-1)" }}>
        <Icon size="xl"><PlusCircleSvg /></Icon>
        <span style={{ fontSize: "var(--font-size-2xs)", color: "var(--text-muted)" }}>xl 24px</span>
      </div>
    </div>
  ),
}
