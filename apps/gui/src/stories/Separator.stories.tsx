import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { Separator } from "@/components/ui/separator";

const meta: Meta<typeof Separator> = {
  title: "Primitives/Separator",
  component: Separator,
  parameters: { layout: "centered" },
  argTypes: {
    orientation: {
      control: { type: "radio" },
      options: ["horizontal", "vertical"],
    },
  },
};
export default meta;

type Story = StoryObj<typeof Separator>;

export const Default: Story = {
  name: "Default (controls)",
  args: {
    orientation: "horizontal",
  },
  render: (args) => (
    <div style={{ width: "256px" }}>
      {args.orientation === "horizontal" ? (
        <>
          <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)", marginBottom: "var(--space-3)" }}>
            Above the separator
          </p>
          <Separator orientation="horizontal" />
          <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)", marginTop: "var(--space-3)" }}>
            Below the separator
          </p>
        </>
      ) : (
        <div style={{ display: "flex", alignItems: "center", height: "32px", gap: "var(--space-3)" }}>
          <span style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>Left</span>
          <Separator orientation="vertical" />
          <span style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>Right</span>
        </div>
      )}
    </div>
  ),
};

export const Horizontal: Story = {
  name: "Horizontal",
  render: () => (
    <div style={{ width: "256px" }}>
      <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)", marginBottom: "var(--space-3)" }}>
        Above the separator
      </p>
      <Separator orientation="horizontal" />
      <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)", marginTop: "var(--space-3)" }}>
        Below the separator
      </p>
    </div>
  ),
};

export const Vertical: Story = {
  name: "Vertical",
  render: () => (
    <div style={{ display: "flex", alignItems: "center", height: "32px", gap: "var(--space-3)" }}>
      <span style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>Left</span>
      <Separator orientation="vertical" />
      <span style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>Right</span>
    </div>
  ),
};
