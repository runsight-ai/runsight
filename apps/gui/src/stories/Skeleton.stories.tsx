import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Primitives/Skeleton",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

export const Text: Story = {
  name: "Variant: text",
  render: () => <div className="skeleton skeleton--text" />,
};

export const TextSm: Story = {
  name: "Variant: text-sm",
  render: () => <div className="skeleton skeleton--text-sm" />,
};

export const Heading: Story = {
  name: "Variant: heading",
  render: () => <div className="skeleton skeleton--heading" />,
};

export const Avatar: Story = {
  name: "Variant: avatar",
  render: () => <div className="skeleton skeleton--avatar" />,
};

export const Button: Story = {
  name: "Variant: button",
  render: () => <div className="skeleton skeleton--button" />,
};

export const AllVariants: Story = {
  name: "All Variants",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)", padding: "var(--space-4)", width: "288px" }}>
      <div className="skeleton skeleton--heading" />
      <div className="skeleton skeleton--text" />
      <div className="skeleton skeleton--text-sm" />
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
        <div className="skeleton skeleton--avatar" />
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
          <div className="skeleton skeleton--text" />
          <div className="skeleton skeleton--text-sm" />
        </div>
      </div>
      <div className="skeleton skeleton--button" />
    </div>
  ),
};
