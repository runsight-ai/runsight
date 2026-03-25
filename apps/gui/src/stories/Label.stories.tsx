import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";

const meta: Meta<typeof Label> = {
  title: "Primitives/Label",
  component: Label,
  parameters: {
    layout: "centered",
  },
};

export default meta;

type Story = StoryObj<typeof Label>;

export const Default: Story = {
  args: {
    children: "Workflow Name",
  },
};

export const WithInput: Story = {
  render: () => (
    <div className="flex flex-col gap-1.5 w-64">
      <Label htmlFor="workflow-name">Workflow Name</Label>
      <Input id="workflow-name" placeholder="e.g. customer-support-triage" />
    </div>
  ),
};

export const Required: Story = {
  render: () => (
    <div className="flex flex-col gap-1.5 w-64">
      <Label htmlFor="api-key">
        API Key <span aria-hidden="true" className="text-danger-9">*</span>
      </Label>
      <Input id="api-key" placeholder="sk-..." type="password" />
    </div>
  ),
};

export const Disabled: Story = {
  render: () => (
    <div className="group flex flex-col gap-1.5 w-64" data-disabled="true">
      <Label htmlFor="disabled-field">Disabled Field</Label>
      <Input id="disabled-field" placeholder="Not editable" disabled />
    </div>
  ),
};
