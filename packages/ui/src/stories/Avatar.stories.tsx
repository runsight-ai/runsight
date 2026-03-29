import type { Meta, StoryObj } from "@storybook/react"
import React from "react"

import { Avatar, AvatarGroup } from "../components/ui/avatar"

const meta: Meta<typeof Avatar> = {
  title: "Primitives/Avatar",
  component: Avatar,
  parameters: { layout: "centered" },
  argTypes: {
    size: {
      control: { type: "select" },
      options: ["sm", "default", "lg"],
      description: "Avatar size variant",
    },
    src: {
      control: "text",
      description: "Image URL. When provided, renders an img element.",
    },
    alt: {
      control: "text",
      description: "Alt text for the avatar image",
    },
    children: {
      control: "text",
      description: "Initials fallback when no src is provided",
    },
  },
}
export default meta

type Story = StoryObj<typeof Avatar>

export const Default: Story = {
  name: "Default (controls)",
  args: {
    size: "default",
    children: "NR",
  },
}

export const AllSizes: Story = {
  name: "All Sizes",
  render: () => (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)" }}>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--space-1)" }}>
        <Avatar size="sm">NR</Avatar>
        <span style={{ fontSize: "var(--font-size-2xs)", color: "var(--text-muted)" }}>sm</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--space-1)" }}>
        <Avatar size="default">MR</Avatar>
        <span style={{ fontSize: "var(--font-size-2xs)", color: "var(--text-muted)" }}>default</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--space-1)" }}>
        <Avatar size="lg">AB</Avatar>
        <span style={{ fontSize: "var(--font-size-2xs)", color: "var(--text-muted)" }}>lg</span>
      </div>
    </div>
  ),
}

export const WithImage: Story = {
  name: "With Image",
  render: () => (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
      <Avatar
        size="sm"
        src="https://avatars.githubusercontent.com/u/1?v=4"
        alt="GitHub user"
      />
      <Avatar
        size="default"
        src="https://avatars.githubusercontent.com/u/2?v=4"
        alt="GitHub user"
      />
      <Avatar
        size="lg"
        src="https://avatars.githubusercontent.com/u/3?v=4"
        alt="GitHub user"
      />
    </div>
  ),
}

export const Group: Story = {
  name: "Group",
  render: () => (
    <AvatarGroup>
      <Avatar size="sm">D</Avatar>
      <Avatar size="sm">C</Avatar>
      <Avatar size="sm">B</Avatar>
      <Avatar size="sm">A</Avatar>
    </AvatarGroup>
  ),
}
