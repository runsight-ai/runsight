import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

type TooltipPosition = "top" | "bottom";

interface TooltipProps {
  position: TooltipPosition;
  label: string;
}

function TooltipDemo({ position, label }: TooltipProps) {
  return (
    <div style={{ padding: "var(--space-12)" }}>
      <div className="tooltip-trigger">
        <button className="btn btn--secondary btn--sm">Hover me</button>
        <span className={`tooltip-content tooltip-content--${position}`} style={{ opacity: 1 }}>
          {label}
        </span>
      </div>
    </div>
  );
}

const meta: Meta<TooltipProps> = {
  title: "Primitives/Tooltip",
  component: TooltipDemo,
  parameters: { layout: "centered" },
  argTypes: {
    position: {
      control: { type: "radio" },
      options: ["top", "bottom"],
    },
    label: { control: "text" },
  },
};
export default meta;

type Story = StoryObj<TooltipProps>;

export const Default: Story = {
  name: "Default (controls)",
  args: {
    position: "bottom",
    label: "This is a tooltip",
  },
};

export const Simple: Story = {
  name: "Simple — text only",
  render: () => (
    <div style={{ padding: "var(--space-12)" }}>
      <div className="tooltip-trigger">
        <button className="btn btn--ghost btn--sm">Hover for hint</button>
        <span className="tooltip-content tooltip-content--top" style={{ opacity: 1 }}>
          Trigger a manual workflow run
        </span>
      </div>
    </div>
  ),
};

export const Rich: Story = {
  name: "Rich — soul tooltip",
  render: () => (
    <div style={{ padding: "160px var(--space-12) var(--space-12)" }}>
      <div className="soul-tip-wrap">
        <span
          className="node-card__avatar"
          style={{ background: "hsl(38, 85%, 45%)", width: 28, height: 28, fontSize: 11 }}
        >
          W
        </span>
        {/* Pinned visible for Storybook demo */}
        <span className="soul-tip" style={{ opacity: 1 }}>
          <span className="soul-tip__name">
            <span className="soul-tip__dot" style={{ background: "hsl(38, 85%, 45%)" }} />
            writer_main
          </span>
          <span className="soul-tip__row">
            <span className="soul-tip__key">Model</span>
            <span className="soul-tip__val">gpt-4o</span>
          </span>
          <span className="soul-tip__row">
            <span className="soul-tip__key">Provider</span>
            <span className="soul-tip__val">OpenAI</span>
          </span>
          <span className="soul-tip__row">
            <span className="soul-tip__key">Cost/1K</span>
            <span className="soul-tip__val">$0.005</span>
          </span>
          <span className="soul-tip__prompt">
            Generate a first draft from the structured brief, focusing on clarity and completeness.
          </span>
        </span>
      </div>
    </div>
  ),
};

export const WithIconButton: Story = {
  name: "Icon button with tooltip",
  render: () => (
    <div style={{ padding: "var(--space-12)" }}>
      <div className="tooltip-trigger">
        <button className="btn btn--secondary btn--icon btn--sm" aria-label="Settings">
          <span className="icon icon--md">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
              <path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </span>
        </button>
        <span className="tooltip-content tooltip-content--top" style={{ opacity: 1 }}>Settings</span>
      </div>
    </div>
  ),
};
