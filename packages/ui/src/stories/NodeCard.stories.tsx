import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { NodeCard } from "../components/ui/node-card";
import type { BlockCategory, ExecutionState } from "../components/ui/node-card";
import {
  SparklesIcon,
  ArrowRightLeftIcon,
  RepeatIcon,
  WrenchIcon,
  PuzzleIcon,
  GitBranchIcon,
  GlobeIcon,
  FileTextIcon,
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
    inputPort: true,
    outputPort: true,
    meta: "Linear",
    soul: {
      initial: "R",
      color: "hsl(38, 85%, 45%)",
      name: "researcher",
      model: "gpt-4o",
      provider: "OpenAI",
    },
  },
};

export const AllCategories: Story = {
  name: "All Categories",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", width: "260px" }}>
      <NodeCard title="Research Agent" category="block-agent" icon={<SparklesIcon size={14} />} inputPort outputPort meta="Linear" soul={{ initial: "R", color: "hsl(38, 85%, 45%)", name: "researcher", model: "gpt-4o", provider: "OpenAI" }} cost="$0.0024" />
      <NodeCard title="Route Decision" category="block-logic" icon={<ArrowRightLeftIcon size={14} />} inputPort outputPort meta="Gate" />
      <NodeCard title="Loop Until" category="block-control" icon={<RepeatIcon size={14} />} inputPort outputPort meta="Control" />
      <NodeCard title="Format Output" category="block-utility" icon={<WrenchIcon size={14} />} inputPort outputPort meta="Utility" />
      <NodeCard title="My Custom Block" category="block-custom" icon={<PuzzleIcon size={14} />} inputPort outputPort meta="Custom" />
    </div>
  ),
};

export const AllStates: Story = {
  name: "All Execution States",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", width: "260px" }}>
      <NodeCard title="Idle" category="block-agent" executionState="idle" icon={<SparklesIcon size={14} />} inputPort outputPort meta="Linear" soul={{ initial: "A", color: "hsl(38, 85%, 45%)", name: "agent", model: "gpt-4o", provider: "OpenAI" }} />
      <NodeCard title="Running" category="block-agent" executionState="running" icon={<SparklesIcon size={14} />} inputPort outputPort meta="Linear" soul={{ initial: "A", color: "hsl(38, 85%, 45%)", name: "agent", model: "gpt-4o", provider: "OpenAI" }} />
      <NodeCard title="Success" category="block-agent" executionState="success" icon={<SparklesIcon size={14} />} inputPort outputPort meta="Linear" soul={{ initial: "A", color: "hsl(38, 85%, 45%)", name: "agent", model: "gpt-4o", provider: "OpenAI" }} />
      <NodeCard title="Error" category="block-agent" executionState="error" icon={<SparklesIcon size={14} />} inputPort outputPort meta="Linear" soul={{ initial: "A", color: "hsl(38, 85%, 45%)", name: "agent", model: "gpt-4o", provider: "OpenAI" }} />
      <NodeCard title="Skipped" category="block-agent" executionState="skipped" icon={<SparklesIcon size={14} />} inputPort outputPort meta="Linear" soul={{ initial: "A", color: "hsl(38, 85%, 45%)", name: "agent", model: "gpt-4o", provider: "OpenAI" }} />
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
      inputPort
      outputPort
      meta="Linear"
      soul={{ initial: "R", color: "hsl(38, 85%, 45%)", name: "researcher", model: "gpt-4o", provider: "OpenAI" }}
    />
  ),
};

export const WithPorts: Story = {
  name: "With Ports — 2-port gate (.node-card__port-rows)",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", width: "260px" }}>
      {/* 2-port pass/fail gate — .node-card__port-row-dot--pass / --fail */}
      <NodeCard
        title="Quality Gate"
        category="block-logic"
        icon={<ArrowRightLeftIcon size={14} />}
        inputPort
        meta={["Gate", "2 ports"]}
        ports={[
          { name: "pass", type: "pass" },
          { name: "fail", type: "fail" },
        ]}
      />

      {/* 3-route dispatch example — default dot colour */}
      <NodeCard
        title="Intent Dispatch"
        category="block-logic"
        icon={<GitBranchIcon size={14} />}
        inputPort
        meta={["Dispatch", "3 routes"]}
        ports={[
          { name: "support", type: "default" },
          { name: "sales", type: "default" },
          { name: "billing", type: "default" },
        ]}
      />
    </div>
  ),
};

export const WithSoul: Story = {
  name: "With Soul — avatar + soul-tip (.node-card__avatar-stack)",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", width: "260px" }}>
      {/* Writer soul */}
      <NodeCard
        title="Summarize Input"
        category="block-agent"
        icon={<SparklesIcon size={14} />}
        inputPort
        outputPort
        meta="Linear"
        soul={{
          initial: "W",
          color: "hsl(38, 85%, 45%)",
          name: "writer_main",
          model: "gpt-4o",
          provider: "OpenAI",
          prompt: "Summarize the user input into a structured brief for downstream agents.",
        }}
      />

      {/* Evaluator soul */}
      <NodeCard
        title="Draft & Evaluate"
        category="block-agent"
        executionState="running"
        icon={<SparklesIcon size={14} />}
        inputPort
        outputPort
        meta="Fanout"
        soul={{
          initial: "E",
          color: "hsl(142, 55%, 42%)",
          name: "evaluator_quality",
          model: "claude-sonnet-4",
          provider: "Anthropic",
          prompt: "Score the draft on coherence, accuracy, and style.",
        }}
      />
    </div>
  ),
};

export const WithStatusBadge: Story = {
  name: "With Status Badge (.node-card__status-badge)",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", width: "260px" }}>
      <NodeCard
        title="Quality Gate"
        category="block-logic"
        executionState="running"
        icon={<ArrowRightLeftIcon size={14} />}
        inputPort
        outputPort
        meta="Gate"
        statusBadge="Running"
        soul={{
          initial: "E",
          color: "hsl(142, 55%, 42%)",
          name: "evaluator_quality",
          model: "claude-sonnet-4",
          provider: "Anthropic",
        }}
        cost="$0.0014"
      />

      <NodeCard
        title="Write Draft"
        category="block-agent"
        executionState="success"
        icon={<SparklesIcon size={14} />}
        inputPort
        outputPort
        meta="Linear"
        statusBadge="Completed"
        soul={{
          initial: "W",
          color: "hsl(38, 85%, 45%)",
          name: "writer_main",
          model: "gpt-4o",
          provider: "OpenAI",
        }}
        cost="$0.0031"
      />

      <NodeCard
        title="HTTP Request"
        category="block-control"
        executionState="error"
        icon={<GlobeIcon size={14} />}
        inputPort
        outputPort
        meta="HTTP"
        statusBadge="Failed"
      />
    </div>
  ),
};

export const FullExample: Story = {
  name: "Full Example — all BEM elements",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-8)", width: "260px" }}>
      {/* Agent node with soul, meta, input+output ports, cost */}
      <NodeCard
        title="Summarize Input"
        category="block-agent"
        icon={<SparklesIcon size={14} />}
        inputPort
        outputPort
        meta="Linear"
        soul={{
          initial: "W",
          color: "hsl(38, 85%, 45%)",
          name: "writer_main",
          model: "gpt-4o",
          provider: "OpenAI",
          rows: [{ key: "Cost/1K", val: "$0.005" }],
          prompt: "Summarize the user input into a structured brief for downstream agents.",
        }}
      />

      {/* Logic gate with pass/fail port rows */}
      <NodeCard
        title="Quality Gate"
        category="block-logic"
        executionState="running"
        icon={<ArrowRightLeftIcon size={14} />}
        inputPort
        statusBadge="Running"
        meta={["Gate", "2 ports"]}
        soul={{
          initial: "E",
          color: "hsl(142, 55%, 42%)",
          name: "evaluator_quality",
          model: "claude-sonnet-4",
          provider: "Anthropic",
        }}
        cost="$0.0014"
        ports={[
          { name: "pass", type: "pass" },
          { name: "fail", type: "fail" },
        ]}
      />

      {/* Fanout with soul and port rows */}
      <NodeCard
        title="Multi-Analyst Fanout"
        category="block-agent"
        icon={<FileTextIcon size={14} />}
        inputPort
        meta={["Fanout", "3 ports"]}
        soul={{
          initial: "TL",
          color: "hsl(38, 85%, 45%)",
          name: "team_lead",
          model: "claude-opus-4",
          provider: "Anthropic",
        }}
        ports={[
          { name: "market", type: "default" },
          { name: "tech", type: "default" },
          { name: "legal", type: "default" },
        ]}
      />
    </div>
  ),
};
