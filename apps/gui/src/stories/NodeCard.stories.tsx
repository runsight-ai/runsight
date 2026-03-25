import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { NodeCard } from "@/components/ui/node-card";
import type { BlockCategory, ExecutionState } from "@/components/ui/node-card";
import {
  SparklesIcon,
  ArrowRightLeftIcon,
  RepeatIcon,
  WrenchIcon,
  PuzzleIcon,
} from "lucide-react";

const meta: Meta<typeof NodeCard> = {
  title: "Composites/NodeCard",
  component: NodeCard,
  parameters: { layout: "centered" },
  argTypes: {
    title: { control: "text" },
    category: {
      control: { type: "select" },
      options: ["block-agent", "block-logic", "block-control", "block-utility", "block-custom"] satisfies BlockCategory[],
    },
    executionState: {
      control: { type: "select" },
      options: ["idle", "running", "success", "error", "skipped"] satisfies ExecutionState[],
    },
    selected: { control: "boolean" },
    cost: { control: "text" },
  },
};
export default meta;

type Story = StoryObj<typeof NodeCard>;

export const Default: Story = {
  name: "Default (controls)",
  args: {
    title: "Research Agent",
    category: "block-agent",
    executionState: "idle",
    selected: false,
    cost: "$0.0024",
    icon: <SparklesIcon size={14} />,
  },
};

export const AllCategories: Story = {
  name: "All Categories",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", width: "260px" }}>
      <NodeCard title="Research Agent" category="block-agent" icon={<SparklesIcon size={14} />} cost="$0.0024" />
      <NodeCard title="Route Decision" category="block-logic" icon={<ArrowRightLeftIcon size={14} />} />
      <NodeCard title="Loop Until" category="block-control" icon={<RepeatIcon size={14} />} />
      <NodeCard title="Format Output" category="block-utility" icon={<WrenchIcon size={14} />} />
      <NodeCard title="My Custom Block" category="block-custom" icon={<PuzzleIcon size={14} />} />
    </div>
  ),
};

export const AllStates: Story = {
  name: "All Execution States",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", width: "260px" }}>
      <NodeCard title="Idle" category="block-agent" executionState="idle" icon={<SparklesIcon size={14} />} />
      <NodeCard title="Running" category="block-agent" executionState="running" icon={<SparklesIcon size={14} />} />
      <NodeCard title="Success" category="block-agent" executionState="success" icon={<SparklesIcon size={14} />} />
      <NodeCard title="Error" category="block-agent" executionState="error" icon={<SparklesIcon size={14} />} />
      <NodeCard title="Skipped" category="block-agent" executionState="skipped" icon={<SparklesIcon size={14} />} />
    </div>
  ),
};

export const Selected: Story = {
  name: "Selected",
  render: () => (
    <NodeCard
      title="Research Agent"
      category="block-agent"
      executionState="idle"
      selected
      cost="$0.0012"
      icon={<SparklesIcon size={14} />}
    />
  ),
};

export const WithPorts: Story = {
  name: "With Ports",
  render: () => (
    <NodeCard
      title="Quality Gate"
      category="block-logic"
      icon={<ArrowRightLeftIcon size={14} />}
      inputPort={<span style={{ fontSize: "var(--font-size-2xs)", color: "var(--text-muted)" }}>in</span>}
      outputPort={<span style={{ fontSize: "var(--font-size-2xs)", color: "var(--text-muted)" }}>out</span>}
    />
  ),
};

export const WithSoul: Story = {
  name: "With Soul / Body Content",
  render: () => (
    <NodeCard
      title="Draft & Evaluate"
      category="block-agent"
      executionState="running"
      cost="$0.0008"
      icon={<SparklesIcon size={14} />}
    >
      <span style={{ fontSize: "var(--font-size-2xs)", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
        writer_main · gpt-4o
      </span>
    </NodeCard>
  ),
};
