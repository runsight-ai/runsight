import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { Switch } from "@/components/ui/switch";

const meta: Meta<typeof Switch> = {
  title: "Form Controls/Switch",
  component: Switch,
  parameters: {
    layout: "centered",
  },
  argTypes: {
    disabled: { control: "boolean" },
    size: {
      control: "select",
      options: ["default", "sm"],
    },
  },
};

export default meta;

type Story = StoryObj<typeof Switch>;

export const Default: Story = {
  args: {
    "aria-label": "Enable feature",
  },
};

export const Checked: Story = {
  args: {
    defaultChecked: true,
    "aria-label": "Feature enabled",
  },
};

export const Unchecked: Story = {
  args: {
    defaultChecked: false,
    "aria-label": "Feature disabled",
  },
};

export const On: Story = {
  args: {
    defaultChecked: true,
    "aria-label": "On state",
  },
};

export const Off: Story = {
  args: {
    defaultChecked: false,
    "aria-label": "Off state",
  },
};

export const Small: Story = {
  args: {
    size: "sm",
    defaultChecked: true,
    "aria-label": "Small switch",
  },
};

export const Disabled: Story = {
  args: {
    disabled: true,
    "aria-label": "Disabled switch",
  },
};

export const DisabledChecked: Story = {
  name: "Disabled (Checked)",
  args: {
    disabled: true,
    defaultChecked: true,
    "aria-label": "Disabled and checked switch",
  },
};

export const AllStates: Story = {
  render: () => (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <Switch aria-label="Off" />
        <span className="text-sm text-muted">Off</span>
      </div>
      <div className="flex items-center gap-3">
        <Switch defaultChecked aria-label="On" />
        <span className="text-sm text-muted">On</span>
      </div>
      <div className="flex items-center gap-3">
        <Switch disabled aria-label="Disabled off" />
        <span className="text-sm text-muted">Disabled Off</span>
      </div>
      <div className="flex items-center gap-3">
        <Switch disabled defaultChecked aria-label="Disabled on" />
        <span className="text-sm text-muted">Disabled On</span>
      </div>
    </div>
  ),
};
