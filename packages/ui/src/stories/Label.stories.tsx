import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { Label } from "../components/ui/label";

const meta: Meta<typeof Label> = {
  title: "Forms/Label",
  component: Label,
  parameters: { layout: "centered" },
  argTypes: {
    required: { control: "boolean" },
    children: { control: "text" },
  },
};
export default meta;

type Story = StoryObj<typeof Label>;

export const Default: Story = {
  name: "Default (controls)",
  args: {
    required: false,
    children: "Workflow Name",
  },
};

export const Required: Story = {
  name: "Required",
  args: {
    required: true,
    children: "API Key",
  },
};

export const Disabled: Story = {
  name: "Disabled (with field group)",
  render: () => (
    <div className="group" data-disabled="true" style={{ width: "256px" }}>
      <Label htmlFor="disabled-field">Disabled Field</Label>
      <input
        className="input input--disabled"
        id="disabled-field"
        type="text"
        placeholder="Not editable"
        disabled
      />
    </div>
  ),
};

export const WithInput: Story = {
  name: "With Input",
  render: () => (
    <div className="field" style={{ width: "256px" }}>
      <Label htmlFor="workflow-name">Workflow Name</Label>
      <input className="input" id="workflow-name" type="text" placeholder="e.g. customer-support-triage" />
    </div>
  ),
};
