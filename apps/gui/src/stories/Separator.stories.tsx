import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { Separator } from "@/components/ui/separator";

const meta: Meta<typeof Separator> = {
  title: "Primitives/Separator",
  component: Separator,
  parameters: {
    layout: "centered",
  },
  argTypes: {
    orientation: {
      control: "select",
      options: ["horizontal", "vertical"],
    },
  },
};

export default meta;

type Story = StoryObj<typeof Separator>;

export const Horizontal: Story = {
  render: () => (
    <div className="w-64">
      <p className="text-sm text-secondary">Above the separator</p>
      <Separator orientation="horizontal" className="my-3" />
      <p className="text-sm text-secondary">Below the separator</p>
    </div>
  ),
};

export const Vertical: Story = {
  render: () => (
    <div className="flex items-center h-8 gap-3">
      <span className="text-sm text-secondary">Left</span>
      <Separator orientation="vertical" />
      <span className="text-sm text-secondary">Right</span>
    </div>
  ),
};

export const InToolbar: Story = {
  name: "In Toolbar",
  render: () => (
    <div className="flex items-center gap-2 px-3 h-10 rounded-radius-md border border-border-default">
      <button className="text-sm text-secondary hover:text-primary">File</button>
      <button className="text-sm text-secondary hover:text-primary">Edit</button>
      <Separator orientation="vertical" />
      <button className="text-sm text-secondary hover:text-primary">View</button>
      <Separator orientation="vertical" />
      <button className="text-sm text-secondary hover:text-primary">Help</button>
    </div>
  ),
};
