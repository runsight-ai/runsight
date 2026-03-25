import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Primitives/Button",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

export const Primary: Story = {
  render: () => <button className="btn btn--primary btn--sm">Save Workflow</button>,
};

export const Secondary: Story = {
  render: () => <button className="btn btn--secondary btn--sm">Cancel</button>,
};

export const Ghost: Story = {
  render: () => <button className="btn btn--ghost btn--sm">Reset</button>,
};

export const Danger: Story = {
  render: () => <button className="btn btn--danger btn--sm">Delete Workflow</button>,
};

export const IconOnly: Story = {
  name: "Icon Only",
  render: () => (
    <button className="btn btn--secondary btn--icon btn--sm" aria-label="Settings">
      <span className="icon icon--md">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
          <path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      </span>
    </button>
  ),
};

export const Loading: Story = {
  render: () => <button className="btn btn--primary btn--sm btn--loading">Saving...</button>,
};

export const Disabled: Story = {
  render: () => <button className="btn btn--primary btn--sm" disabled>Disabled</button>,
};

export const Sizes: Story = {
  render: () => (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
      <button className="btn btn--primary btn--xs">XS</button>
      <button className="btn btn--primary btn--sm">SM</button>
      <button className="btn btn--primary btn--md">MD</button>
      <button className="btn btn--primary btn--lg">LG</button>
    </div>
  ),
};

export const AllVariants: Story = {
  render: () => (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
      <button className="btn btn--primary">Primary</button>
      <button className="btn btn--secondary">Secondary</button>
      <button className="btn btn--ghost">Ghost</button>
      <button className="btn btn--danger">Danger</button>
    </div>
  ),
};
