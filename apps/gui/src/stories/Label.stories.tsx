import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Forms/Label",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <label className="field__label">Workflow Name</label>
  ),
};

export const WithInput: Story = {
  render: () => (
    <div className="field" style={{ width: "256px" }}>
      <label className="field__label" htmlFor="workflow-name">Workflow Name</label>
      <input className="input" id="workflow-name" type="text" placeholder="e.g. customer-support-triage" />
    </div>
  ),
};

export const Required: Story = {
  render: () => (
    <div className="field" style={{ width: "256px" }}>
      <label className="field__label field__label--required" htmlFor="api-key">API Key</label>
      <input className="input" id="api-key" type="password" placeholder="sk-..." />
    </div>
  ),
};

export const Disabled: Story = {
  render: () => (
    <div className="field" style={{ width: "256px" }}>
      <label className="field__label" htmlFor="disabled-field" style={{ opacity: 0.5 }}>Disabled Field</label>
      <input className="input input--disabled" id="disabled-field" type="text" placeholder="Not editable" disabled />
    </div>
  ),
};
