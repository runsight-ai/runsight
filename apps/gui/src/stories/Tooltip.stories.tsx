import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
  SoulTip,
} from "@/components/ui/tooltip";

// Wrapper component to expose side/content as Storybook controls
interface TooltipDemoProps {
  side: "top" | "bottom";
  content: string;
  triggerLabel: string;
}

function TooltipDemo({ side, content, triggerLabel }: TooltipDemoProps) {
  return (
    <div style={{ padding: "var(--space-12)" }}>
      <TooltipProvider delay={200}>
        <Tooltip>
          <TooltipTrigger>
            <Button variant="secondary" size="sm">{triggerLabel}</Button>
          </TooltipTrigger>
          <TooltipContent side={side}>{content}</TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>
  );
}

const meta: Meta<TooltipDemoProps> = {
  title: "Primitives/Tooltip",
  component: TooltipDemo,
  parameters: { layout: "centered" },
  argTypes: {
    side: {
      control: { type: "radio" },
      options: ["top", "bottom"],
    },
    content: { control: "text" },
    triggerLabel: { control: "text" },
  },
};
export default meta;

type Story = StoryObj<TooltipDemoProps>;

export const Default: Story = {
  name: "Default (hover to show)",
  args: {
    side: "top",
    content: "This is a tooltip",
    triggerLabel: "Hover me",
  },
};

export const Positions: Story = {
  name: "Positions — top & bottom",
  render: () => (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-8)", padding: "var(--space-16)" }}>
      <TooltipProvider delay={0}>
        <Tooltip>
          <TooltipTrigger>
            <Button variant="secondary" size="sm">Top</Button>
          </TooltipTrigger>
          <TooltipContent side="top">Tooltip on top</TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <TooltipProvider delay={0}>
        <Tooltip>
          <TooltipTrigger>
            <Button variant="secondary" size="sm">Bottom</Button>
          </TooltipTrigger>
          <TooltipContent side="bottom">Tooltip on bottom</TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>
  ),
};

export const RichSoulTip: Story = {
  name: "Rich Soul Tip (soul-tip BEM)",
  render: () => (
    <div
      style={{
        display: "flex",
        alignItems: "flex-end",
        gap: "var(--space-6)",
        padding: "var(--space-24)",
        paddingTop: "var(--space-32)",
      }}
    >
      {/* Writer soul */}
      <div className="node-card__avatar-stack">
        <SoulTip
          initial="W"
          color="hsl(38, 85%, 45%)"
          name="writer_main"
          model="gpt-4o"
          provider="OpenAI"
          prompt="Generate a first draft from the structured brief, focusing on clarity and completeness."
        />
      </div>

      {/* Evaluator soul */}
      <div className="node-card__avatar-stack">
        <SoulTip
          initial="E"
          color="hsl(142, 55%, 42%)"
          name="evaluator_quality"
          model="claude-sonnet-4"
          provider="Anthropic"
          prompt="Score the draft on coherence, accuracy, and style. Return pass/fail with reasoning."
        />
      </div>

      {/* Analyst soul */}
      <div className="node-card__avatar-stack">
        <SoulTip
          initial="A"
          color="hsl(210, 60%, 50%)"
          name="analyst_legal"
          model="gemini-2.0-flash"
          provider="Google"
          prompt="Review for legal compliance, IP risks, and regulatory requirements."
        />
      </div>
    </div>
  ),
};
