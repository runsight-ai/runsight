import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";

type ScrollAreaStoryArgs = { orientation: "vertical" | "horizontal" }

const meta: Meta<ScrollAreaStoryArgs> = {
  title: "Overlays/ScrollArea",
  component: ScrollArea,
  parameters: { layout: "centered" },
  argTypes: {
    orientation: {
      control: { type: "select" },
      options: ["vertical", "horizontal"],
      description: "Scroll direction for the ScrollBar",
    },
  },
};
export default meta;

type Story = StoryObj<ScrollAreaStoryArgs>;

const longContent = Array.from({ length: 40 }, (_, i) => `Item ${i + 1} — workflow step or log entry`);

export const Default: Story = {
  name: "Default (controls)",
  args: {
    orientation: "vertical",
  },
  render: (args) => (
    <ScrollArea
      style={{
        height: "288px",
        width: "256px",
        borderRadius: "var(--radius-lg)",
        border: "1px solid var(--border-default)",
        background: "var(--surface-primary)",
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)", padding: "var(--space-2)" }}>
        {longContent.map((item, i) => (
          <div
            key={i}
            style={{
              padding: "var(--space-1) var(--space-2)",
              fontSize: "var(--font-size-sm)",
              color: "var(--text-primary)",
              borderRadius: "var(--radius-sm)",
              cursor: "default",
            }}
          >
            {item}
          </div>
        ))}
      </div>
      <ScrollBar orientation={args.orientation} />
    </ScrollArea>
  ),
};

export const Horizontal: Story = {
  name: "Horizontal",
  render: () => (
    <ScrollArea
      style={{
        width: "320px",
        borderRadius: "var(--radius-lg)",
        border: "1px solid var(--border-default)",
      }}
    >
      <div style={{ display: "flex", gap: "var(--space-3)", padding: "var(--space-3)", width: "max-content" }}>
        {Array.from({ length: 10 }, (_, i) => (
          <div
            key={i}
            style={{
              width: "128px",
              flexShrink: 0,
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-default)",
              background: "var(--surface-secondary)",
              padding: "var(--space-3)",
            }}
          >
            <p style={{ fontWeight: "var(--font-weight-medium)", fontSize: "var(--font-size-sm)", color: "var(--text-primary)", margin: 0 }}>
              Step {i + 1}
            </p>
            <p style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", marginTop: "var(--space-1)", marginBottom: 0 }}>
              agent-soul-{i + 1}
            </p>
          </div>
        ))}
      </div>
      <ScrollBar orientation="horizontal" />
    </ScrollArea>
  ),
};
