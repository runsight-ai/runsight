import type { Meta, StoryObj } from "@storybook/react"
import React from "react"

import { Link } from "../components/ui/link"

const meta: Meta<typeof Link> = {
  title: "Primitives/Link",
  component: Link,
  parameters: { layout: "centered" },
  argTypes: {
    variant: {
      control: { type: "select" },
      options: ["default", "muted", "external"],
      description: "Link style variant",
    },
    href: {
      control: "text",
      description: "Link href",
    },
    children: {
      control: "text",
      description: "Link text",
    },
  },
}
export default meta

type Story = StoryObj<typeof Link>

export const Default: Story = {
  name: "Default (controls)",
  args: {
    variant: "default",
    href: "#",
    children: "Accent link",
  },
}

export const Muted: Story = {
  name: "Muted",
  render: () => (
    <Link variant="muted" href="#">
      Muted link
    </Link>
  ),
}

export const External: Story = {
  name: "External",
  render: () => (
    <Link variant="external" href="https://runsight.io" target="_blank" rel="noopener noreferrer">
      External link
    </Link>
  ),
}

export const AllVariants: Story = {
  name: "All Variants",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <Link variant="default" href="#">Accent link</Link>
      <Link variant="muted" href="#">Muted link</Link>
      <Link variant="external" href="#">External link</Link>
    </div>
  ),
}
