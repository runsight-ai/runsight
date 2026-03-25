import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

const meta: Meta<{ side: "top" | "bottom" | "left" | "right"; align: "start" | "center" | "end" }> = {
  title: "Overlays/Popover",
  parameters: { layout: "centered" },
  argTypes: {
    side: {
      control: { type: "select" },
      options: ["top", "bottom", "left", "right"],
      description: "Which side of the trigger the popover appears on",
    },
    align: {
      control: { type: "select" },
      options: ["start", "center", "end"],
      description: "Alignment of the popover relative to the trigger",
    },
  },
};
export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  name: "Default (with trigger)",
  args: {
    side: "bottom",
    align: "center",
  },
  render: (args) => (
    <Popover>
      <PopoverTrigger render={<Button variant="secondary">Open Popover</Button>} />
      <PopoverContent side={args.side} align={args.align}>
        <div style={{ marginBottom: "var(--space-2)" }}>
          <div style={{ fontSize: "var(--font-size-md)", fontWeight: "var(--font-weight-semibold)", color: "var(--text-heading)" }}>
            Soul Configuration
          </div>
          <div style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)", marginTop: "var(--space-0-5)" }}>
            Adjust the active soul for this step.
          </div>
        </div>
        <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-muted)", margin: 0 }}>
          Select a soul from the list or create a new one.
        </p>
      </PopoverContent>
    </Popover>
  ),
};

export const WithForm: Story = {
  name: "With Form",
  render: () => (
    <Popover>
      <PopoverTrigger render={<Button variant="secondary">Filter Results</Button>} />
      <PopoverContent>
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", minWidth: "220px" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
            <Label htmlFor="pop-status">Status</Label>
            <select id="pop-status" className="input" style={{ height: "var(--control-height-sm)" }}>
              <option value="">All statuses</option>
              <option value="running">Running</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
            </select>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
            <Label htmlFor="pop-model">Model</Label>
            <select id="pop-model" className="input" style={{ height: "var(--control-height-sm)" }}>
              <option value="">All models</option>
              <option value="sonnet">Claude Sonnet</option>
              <option value="opus">Claude Opus</option>
            </select>
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}>
            <Button variant="ghost" size="sm">Reset</Button>
            <Button variant="primary" size="sm">Apply</Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  ),
};
