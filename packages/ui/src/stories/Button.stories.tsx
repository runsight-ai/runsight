import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { Button } from "../components/ui/button";

const meta: Meta<typeof Button> = {
  title: "Primitives/Button",
  component: Button,
  parameters: { layout: "centered" },
  argTypes: {
    variant: {
      control: { type: "select" },
      options: ["primary", "secondary", "ghost", "danger", "icon-only"],
    },
    size: {
      control: { type: "select" },
      options: ["xs", "sm", "md", "lg"],
    },
    loading: { control: "boolean" },
    disabled: { control: "boolean" },
    children: { control: "text" },
  },
};
export default meta;

type Story = StoryObj<typeof Button>;

export const Default: Story = {
  name: "Default (controls)",
  args: {
    variant: "primary",
    size: "sm",
    loading: false,
    disabled: false,
    children: "Save Workflow",
  },
};

export const AllVariants: Story = {
  name: "All Variants",
  render: () => (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
      <Button variant="primary" size="sm">Primary</Button>
      <Button variant="secondary" size="sm">Secondary</Button>
      <Button variant="ghost" size="sm">Ghost</Button>
      <Button variant="danger" size="sm">Danger</Button>
    </div>
  ),
};

export const AllSizes: Story = {
  name: "All Sizes",
  render: () => (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
      <Button variant="primary" size="xs">XS</Button>
      <Button variant="primary" size="sm">SM</Button>
      <Button variant="primary" size="md">MD</Button>
      <Button variant="primary" size="lg">LG</Button>
    </div>
  ),
};

export const Loading: Story = {
  name: "Loading",
  args: {
    variant: "primary",
    size: "sm",
    loading: true,
    children: "Saving…",
  },
};

export const Disabled: Story = {
  name: "Disabled",
  args: {
    variant: "primary",
    size: "sm",
    disabled: true,
    children: "Disabled",
  },
};

const SettingsIcon = () => (
  <svg aria-hidden="true" className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 005 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 005 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.67a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09A1.65 1.65 0 0019.4 15z" />
  </svg>
)

export const IconOnly: Story = {
  name: "Icon Only",
  render: () => (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
      <Button variant="icon-only" size="xs" aria-label="Settings (xs)">
        <SettingsIcon />
      </Button>
      <Button variant="icon-only" size="sm" aria-label="Settings (sm)">
        <SettingsIcon />
      </Button>
      <Button variant="icon-only" size="md" aria-label="Settings (md)">
        <SettingsIcon />
      </Button>
      <Button variant="icon-only" size="lg" aria-label="Settings (lg)">
        <SettingsIcon />
      </Button>
    </div>
  ),
};

export const AllVariantsAndSizes: Story = {
  name: "All Variants × Sizes",
  render: () => {
    const variants = ["primary", "secondary", "ghost", "danger"] as const
    const sizes = ["xs", "sm", "md", "lg"] as const
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        {sizes.map((size) => (
          <div key={size} style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
            <span style={{ width: 24, fontSize: "var(--font-size-xs)", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>{size}</span>
            {variants.map((variant) => (
              <Button key={variant} variant={variant} size={size}>
                {variant.charAt(0).toUpperCase() + variant.slice(1)}
              </Button>
            ))}
            <Button variant="primary" size={size} loading>Loading</Button>
            <Button variant="primary" size={size} disabled>Disabled</Button>
            <Button variant="icon-only" size={size} aria-label="Settings">
              <SettingsIcon />
            </Button>
          </div>
        ))}
      </div>
    )
  },
};
