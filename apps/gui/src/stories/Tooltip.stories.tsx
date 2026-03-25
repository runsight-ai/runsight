import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
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
