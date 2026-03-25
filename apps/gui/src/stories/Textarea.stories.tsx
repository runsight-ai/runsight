import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Forms/Textarea",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <div style={{ width: "320px" }}>
      <textarea className="textarea" rows={4} placeholder="Enter a description…" />
    </div>
  ),
};

export const WithValue: Story = {
  render: () => (
    <div style={{ width: "320px" }}>
      <textarea className="textarea" rows={4} defaultValue="You are a helpful AI assistant that routes customer support tickets based on their content and urgency." />
    </div>
  ),
};

export const Disabled: Story = {
  render: () => (
    <div style={{ width: "320px" }}>
      <textarea className="textarea" rows={3} placeholder="Disabled textarea" disabled />
    </div>
  ),
};

export const CodeVariant: Story = {
  name: "Code Variant",
  render: () => (
    <div style={{ width: "320px" }}>
      <textarea className="textarea textarea--code" rows={6} placeholder="# Enter YAML here…" />
    </div>
  ),
};

export const WithLabel: Story = {
  render: () => (
    <div className="field" style={{ width: "320px" }}>
      <label className="field__label">System Prompt</label>
      <textarea className="textarea" rows={4} placeholder="You are a helpful assistant…" />
      <span className="field__helper">This prompt is injected at the start of every conversation.</span>
    </div>
  ),
};
