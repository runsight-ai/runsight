import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { Slider } from "@/components/ui/slider";

const meta: Meta<typeof Slider> = {
  title: "Form Controls/Slider",
  component: Slider,
  parameters: {
    layout: "centered",
  },
  argTypes: {
    disabled: { control: "boolean" },
    min: { control: "number" },
    max: { control: "number" },
    step: { control: "number" },
  },
};

export default meta;

type Story = StoryObj<typeof Slider>;

export const Default: Story = {
  args: {
    defaultValue: 50,
    min: 0,
    max: 100,
    step: 1,
    "aria-label": "Volume",
    className: "w-64",
  },
};

export const WithValue: Story = {
  render: () => {
    const [value, setValue] = React.useState(40);
    return (
      <div className="flex flex-col gap-2 w-64">
        <div className="flex justify-between text-sm text-muted">
          <span>Temperature</span>
          <span>{value}</span>
        </div>
        <Slider
          value={value}
          min={0}
          max={100}
          step={1}
          onChange={(e) => setValue(Number(e.target.value))}
          aria-label="Temperature"
        />
      </div>
    );
  },
};

export const Steps: Story = {
  args: {
    defaultValue: 3,
    min: 1,
    max: 5,
    step: 1,
    "aria-label": "Rating",
    className: "w-64",
  },
};

export const Disabled: Story = {
  args: {
    defaultValue: 60,
    min: 0,
    max: 100,
    disabled: true,
    "aria-label": "Disabled slider",
    className: "w-64",
  },
};

export const TokenBudget: Story = {
  render: () => {
    const [value, setValue] = React.useState(2048);
    return (
      <div className="flex flex-col gap-2 w-64">
        <div className="flex justify-between text-sm">
          <span>Max tokens</span>
          <span className="text-muted">{value.toLocaleString()}</span>
        </div>
        <Slider
          value={value}
          min={256}
          max={8192}
          step={256}
          onChange={(e) => setValue(Number(e.target.value))}
          aria-label="Max tokens"
        />
        <div className="flex justify-between text-xs text-muted">
          <span>256</span>
          <span>8,192</span>
        </div>
      </div>
    );
  },
};
