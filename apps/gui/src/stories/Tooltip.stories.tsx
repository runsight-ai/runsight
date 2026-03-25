import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Primitives/Tooltip",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <div style={{ padding: "var(--space-8)" }}>
      <div className="tooltip-trigger">
        <button className="btn btn--secondary btn--sm">Hover me</button>
        <span className="tooltip-content tooltip-content--bottom" style={{ opacity: 1 }}>
          This is a tooltip
        </span>
      </div>
    </div>
  ),
};

export const TopPlacement: Story = {
  name: "Top placement",
  render: () => (
    <div style={{ padding: "var(--space-12)" }}>
      <div className="tooltip-trigger">
        <button className="btn btn--ghost btn--sm">Top tooltip</button>
        <span className="tooltip-content tooltip-content--top" style={{ opacity: 1 }}>
          Appears above the trigger
        </span>
      </div>
    </div>
  ),
};

export const BottomPlacement: Story = {
  name: "Bottom placement",
  render: () => (
    <div style={{ padding: "var(--space-12)" }}>
      <div className="tooltip-trigger">
        <button className="btn btn--ghost btn--sm">Bottom tooltip</button>
        <span className="tooltip-content tooltip-content--bottom" style={{ opacity: 1 }}>
          Appears below the trigger
        </span>
      </div>
    </div>
  ),
};

export const WithIconButton: Story = {
  name: "With Icon Button",
  render: () => (
    <div style={{ padding: "var(--space-12)" }}>
      <div className="tooltip-trigger">
        <button className="btn btn--secondary btn--icon btn--sm" aria-label="Settings">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
            <path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </button>
        <span className="tooltip-content tooltip-content--top" style={{ opacity: 1 }}>Settings</span>
      </div>
    </div>
  ),
};
