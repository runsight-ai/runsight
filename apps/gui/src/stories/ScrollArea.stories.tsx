import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";

const meta: Meta = {
  title: "Overlays/ScrollArea",
  parameters: {
    layout: "centered",
  },
};

export default meta;

type Story = StoryObj;

const longContent = Array.from({ length: 40 }, (_, i) => `Item ${i + 1} — workflow step or log entry`);

export const Default: Story = {
  render: () => (
    <ScrollArea className="h-72 w-64 rounded-lg border border-border-default bg-surface-primary p-2">
      <div className="flex flex-col gap-1">
        {longContent.map((item, i) => (
          <div key={i} className="px-2 py-1 text-sm text-primary rounded hover:bg-surface-hover">
            {item}
          </div>
        ))}
      </div>
    </ScrollArea>
  ),
};

export const Basic: Story = {
  render: () => (
    <ScrollArea className="h-48 w-56 rounded-lg border border-border-default">
      <div className="p-3 flex flex-col gap-1">
        {Array.from({ length: 20 }, (_, i) => (
          <p key={i} className="text-sm text-muted">Log line {i + 1}: execution output here</p>
        ))}
      </div>
    </ScrollArea>
  ),
};

export const HorizontalScroll: Story = {
  name: "Horizontal Overflow",
  render: () => (
    <ScrollArea className="w-64 rounded-lg border border-border-default">
      <div className="flex gap-3 p-3" style={{ width: "max-content" }}>
        {Array.from({ length: 12 }, (_, i) => (
          <div
            key={i}
            className="w-32 shrink-0 rounded-md border border-border-default bg-surface-secondary p-3 text-sm text-primary"
          >
            <p className="font-medium">Step {i + 1}</p>
            <p className="text-xs text-muted mt-1">agent-soul-{i + 1}</p>
          </div>
        ))}
      </div>
      <ScrollBar orientation="horizontal" />
    </ScrollArea>
  ),
};

export const BothAxes: Story = {
  name: "Both Axes Scrollable",
  render: () => (
    <ScrollArea className="h-48 w-64 rounded-lg border border-border-default">
      <div className="p-3" style={{ width: "600px" }}>
        {Array.from({ length: 20 }, (_, i) => (
          <p key={i} className="text-sm text-muted whitespace-nowrap py-0.5">
            {"→ ".repeat(3)}Execution log entry {i + 1}: step completed with status OK
          </p>
        ))}
      </div>
      <ScrollBar orientation="horizontal" />
    </ScrollArea>
  ),
};
