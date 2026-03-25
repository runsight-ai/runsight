import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";

const meta: Meta = {
  title: "Overlays/Popover",
  parameters: {
    layout: "centered",
  },
};

export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <Popover>
      <PopoverTrigger render={<Button variant="secondary">Open Popover</Button>} />
      <PopoverContent>
        <PopoverHeader>
          <PopoverTitle>Soul Configuration</PopoverTitle>
          <PopoverDescription>
            Adjust the active soul for this step.
          </PopoverDescription>
        </PopoverHeader>
        <p className="text-sm text-muted">
          Select a soul from the list or create a new one.
        </p>
      </PopoverContent>
    </Popover>
  ),
};

export const AlignStart: Story = {
  name: "Alignment — Start",
  render: () => (
    <Popover>
      <PopoverTrigger render={<Button variant="secondary">Align Start</Button>} />
      <PopoverContent align="start" side="bottom">
        <PopoverHeader>
          <PopoverTitle>Start Aligned</PopoverTitle>
        </PopoverHeader>
        <p className="text-sm text-muted">Popover aligned to the start of the trigger.</p>
      </PopoverContent>
    </Popover>
  ),
};

export const TopPlacement: Story = {
  name: "Placement — Top",
  render: () => (
    <Popover>
      <PopoverTrigger render={<Button variant="secondary">Top Popover</Button>} />
      <PopoverContent side="top" align="center">
        <PopoverHeader>
          <PopoverTitle>Top Placement</PopoverTitle>
        </PopoverHeader>
        <p className="text-sm text-muted">Popover positioned above the trigger.</p>
      </PopoverContent>
    </Popover>
  ),
};

export const RightPlacement: Story = {
  name: "Placement — Right",
  render: () => (
    <Popover>
      <PopoverTrigger render={<Button variant="secondary">Right Popover</Button>} />
      <PopoverContent side="right" align="center">
        <PopoverHeader>
          <PopoverTitle>Right Placement</PopoverTitle>
        </PopoverHeader>
        <p className="text-sm text-muted">Popover positioned to the right of the trigger.</p>
      </PopoverContent>
    </Popover>
  ),
};

export const LeftPlacement: Story = {
  name: "Placement — Left",
  render: () => (
    <Popover>
      <PopoverTrigger render={<Button variant="secondary">Left Popover</Button>} />
      <PopoverContent side="left" align="center">
        <PopoverHeader>
          <PopoverTitle>Left Placement</PopoverTitle>
        </PopoverHeader>
        <p className="text-sm text-muted">Popover positioned to the left of the trigger.</p>
      </PopoverContent>
    </Popover>
  ),
};
