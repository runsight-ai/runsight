import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Forms/Radio",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <div className="radio-group">
      <label className="radio">
        <input className="radio__input" type="radio" name="model-default" value="sonnet" defaultChecked />
        <span className="radio__label">Claude Sonnet</span>
      </label>
      <label className="radio">
        <input className="radio__input" type="radio" name="model-default" value="opus" />
        <span className="radio__label">Claude Opus</span>
      </label>
      <label className="radio">
        <input className="radio__input" type="radio" name="model-default" value="haiku" />
        <span className="radio__label">Claude Haiku</span>
      </label>
    </div>
  ),
};

export const Horizontal: Story = {
  render: () => (
    <div className="radio-group radio-group--horizontal">
      <label className="radio">
        <input className="radio__input" type="radio" name="size-h" value="sm" />
        <span className="radio__label">Small</span>
      </label>
      <label className="radio">
        <input className="radio__input" type="radio" name="size-h" value="md" defaultChecked />
        <span className="radio__label">Medium</span>
      </label>
      <label className="radio">
        <input className="radio__input" type="radio" name="size-h" value="lg" />
        <span className="radio__label">Large</span>
      </label>
    </div>
  ),
};

export const Disabled: Story = {
  render: () => (
    <div className="radio-group">
      <label className="radio">
        <input className="radio__input" type="radio" name="disabled-group" value="a" disabled />
        <span className="radio__label">Option A (disabled)</span>
      </label>
      <label className="radio">
        <input className="radio__input" type="radio" name="disabled-group" value="b" disabled defaultChecked />
        <span className="radio__label">Option B (disabled, checked)</span>
      </label>
    </div>
  ),
};

export const Single: Story = {
  render: () => (
    <label className="radio">
      <input className="radio__input" type="radio" name="single" value="agree" />
      <span className="radio__label">I agree to the terms and conditions</span>
    </label>
  ),
};
