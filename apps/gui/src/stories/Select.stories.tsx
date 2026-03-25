import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Forms/Select",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <div style={{ width: "220px" }}>
      <select className="select">
        <option value="" disabled selected>Select a model</option>
        <option value="claude-3-5-sonnet">Claude 3.5 Sonnet</option>
        <option value="claude-3-opus">Claude 3 Opus</option>
        <option value="claude-3-haiku">Claude 3 Haiku</option>
        <option value="gpt-4o">GPT-4o</option>
        <option value="gpt-4-turbo">GPT-4 Turbo</option>
      </select>
    </div>
  ),
};

export const WithValue: Story = {
  render: () => (
    <div style={{ width: "220px" }}>
      <select className="select" defaultValue="claude-3-5-sonnet">
        <option value="claude-3-5-sonnet">Claude 3.5 Sonnet</option>
        <option value="claude-3-opus">Claude 3 Opus</option>
        <option value="claude-3-haiku">Claude 3 Haiku</option>
      </select>
    </div>
  ),
};

export const Disabled: Story = {
  render: () => (
    <div style={{ width: "220px" }}>
      <select className="select" disabled>
        <option value="">Disabled select</option>
        <option value="a">Option A</option>
      </select>
    </div>
  ),
};

export const WithLabel: Story = {
  render: () => (
    <div className="field" style={{ width: "220px" }}>
      <label className="field__label">Model</label>
      <select className="select">
        <option value="">Select model…</option>
        <option value="claude-3-5-sonnet">Claude 3.5 Sonnet</option>
        <option value="claude-3-opus">Claude 3 Opus</option>
        <option value="gpt-4o">GPT-4o</option>
      </select>
    </div>
  ),
};
