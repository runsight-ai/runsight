import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { NodeCard } from "@/components/ui/node-card";

const meta: Meta<typeof NodeCard> = {
  title: "Composites/NodeCard",
  component: NodeCard,
  parameters: {
    layout: "centered",
  },
  argTypes: {
    category: {
      control: "select",
      options: [
        "block-agent",
        "block-logic",
        "block-control",
        "block-utility",
        "block-custom",
      ],
    },
    executionState: {
      control: "select",
      options: ["idle", "running", "success", "error", "skipped"],
    },
    selected: { control: "boolean" },
  },
};

export default meta;

type Story = StoryObj<typeof NodeCard>;

// ---------------------------------------------------------------------------
// Default
// ---------------------------------------------------------------------------

export const Default: Story = {
  args: {
    title: "Research Agent",
    category: "block-agent",
    executionState: "idle",
    selected: false,
    cost: "$0.0012",
  },
};

// ---------------------------------------------------------------------------
// Block category variants
// ---------------------------------------------------------------------------

export const CategoryAgent: Story = {
  name: "Category — agent",
  args: {
    title: "Research Agent",
    category: "block-agent",
    cost: "$0.0024",
  },
};

export const CategoryLogic: Story = {
  name: "Category — logic",
  args: {
    title: "Route Decision",
    category: "block-logic",
  },
};

export const CategoryControl: Story = {
  name: "Category — control",
  args: {
    title: "Loop Until",
    category: "block-control",
  },
};

export const CategoryUtility: Story = {
  name: "Category — utility",
  args: {
    title: "Format Output",
    category: "block-utility",
  },
};

export const CategoryCustom: Story = {
  name: "Category — custom",
  args: {
    title: "My Custom Block",
    category: "block-custom",
  },
};

// ---------------------------------------------------------------------------
// Execution states
// ---------------------------------------------------------------------------

export const StateRunning: Story = {
  name: "Execution state — running",
  args: {
    title: "Summarise Results",
    category: "block-agent",
    executionState: "running",
    cost: "$0.0008",
  },
};

export const StateSuccess: Story = {
  name: "Execution state — success",
  args: {
    title: "Fetch Data",
    category: "block-utility",
    executionState: "success",
    cost: "$0.0003",
  },
};

export const StateError: Story = {
  name: "Execution state — error / danger",
  args: {
    title: "Validate Schema",
    category: "block-logic",
    executionState: "error",
  },
};

export const StateSkipped: Story = {
  name: "Execution state — skipped",
  args: {
    title: "Optional Enrichment",
    category: "block-control",
    executionState: "skipped",
  },
};

// ---------------------------------------------------------------------------
// Selected state
// ---------------------------------------------------------------------------

export const Selected: Story = {
  name: "Selected state",
  args: {
    title: "Research Agent",
    category: "block-agent",
    executionState: "idle",
    selected: true,
    cost: "$0.0012",
  },
};

// ---------------------------------------------------------------------------
// All categories overview
// ---------------------------------------------------------------------------

export const AllCategories: Story = {
  name: "All block categories",
  render: () => (
    <div className="flex flex-col gap-3" style={{ width: 240 }}>
      <NodeCard title="Research Agent"    category="block-agent"   cost="$0.0024" />
      <NodeCard title="Route Decision"    category="block-logic"   />
      <NodeCard title="Loop Until"        category="block-control" />
      <NodeCard title="Format Output"     category="block-utility" />
      <NodeCard title="My Custom Block"   category="block-custom"  />
    </div>
  ),
};

// ---------------------------------------------------------------------------
// All execution states overview
// ---------------------------------------------------------------------------

export const AllExecutionStates: Story = {
  name: "All execution states",
  render: () => (
    <div className="flex flex-col gap-3" style={{ width: 240 }}>
      <NodeCard title="Idle"    category="block-agent" executionState="idle"    />
      <NodeCard title="Running" category="block-agent" executionState="running" />
      <NodeCard title="Success" category="block-agent" executionState="success" />
      <NodeCard title="Error"   category="block-agent" executionState="error"   />
      <NodeCard title="Skipped" category="block-agent" executionState="skipped" />
    </div>
  ),
};
