import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Primitives/Spinner",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <span className="spinner spinner--md">
      <span className="spinner__circle" />
    </span>
  ),
};

export const Small: Story = {
  name: "Size: sm",
  render: () => (
    <span className="spinner spinner--sm">
      <span className="spinner__circle" />
    </span>
  ),
};

export const Medium: Story = {
  name: "Size: md",
  render: () => (
    <span className="spinner spinner--md">
      <span className="spinner__circle" />
    </span>
  ),
};

export const Large: Story = {
  name: "Size: lg",
  render: () => (
    <span className="spinner spinner--lg">
      <span className="spinner__circle" />
    </span>
  ),
};

export const Accent: Story = {
  name: "Variant: accent",
  render: () => (
    <span className="spinner spinner--md spinner--accent">
      <span className="spinner__circle" />
    </span>
  ),
};

export const AllSizes: Story = {
  name: "All Sizes",
  render: () => (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-6)" }}>
      <span className="spinner spinner--sm"><span className="spinner__circle" /></span>
      <span className="spinner spinner--md"><span className="spinner__circle" /></span>
      <span className="spinner spinner--lg"><span className="spinner__circle" /></span>
    </div>
  ),
};

export const AllVariants: Story = {
  name: "All Variants",
  render: () => (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-6)" }}>
      <span className="spinner spinner--md"><span className="spinner__circle" /></span>
      <span className="spinner spinner--md spinner--accent"><span className="spinner__circle" /></span>
    </div>
  ),
};
