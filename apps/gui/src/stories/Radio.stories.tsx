import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { Radio, RadioGroup } from "@/components/ui/radio";

const meta: Meta = {
  title: "Form Controls/Radio",
  parameters: {
    layout: "centered",
  },
};

export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <RadioGroup>
      <label className="flex items-center gap-2 text-sm cursor-pointer">
        <Radio name="model" value="sonnet" defaultChecked aria-label="Sonnet" />
        <span>Claude Sonnet</span>
      </label>
      <label className="flex items-center gap-2 text-sm cursor-pointer">
        <Radio name="model" value="opus" aria-label="Opus" />
        <span>Claude Opus</span>
      </label>
      <label className="flex items-center gap-2 text-sm cursor-pointer">
        <Radio name="model" value="haiku" aria-label="Haiku" />
        <span>Claude Haiku</span>
      </label>
    </RadioGroup>
  ),
};

export const Vertical: Story = {
  render: () => (
    <RadioGroup orientation="vertical">
      <label className="flex items-center gap-2 text-sm cursor-pointer">
        <Radio name="size-v" value="sm" aria-label="Small" />
        <span>Small</span>
      </label>
      <label className="flex items-center gap-2 text-sm cursor-pointer">
        <Radio name="size-v" value="md" defaultChecked aria-label="Medium" />
        <span>Medium</span>
      </label>
      <label className="flex items-center gap-2 text-sm cursor-pointer">
        <Radio name="size-v" value="lg" aria-label="Large" />
        <span>Large</span>
      </label>
    </RadioGroup>
  ),
};

export const Horizontal: Story = {
  render: () => (
    <RadioGroup orientation="horizontal">
      <label className="flex items-center gap-2 text-sm cursor-pointer">
        <Radio name="size-h" value="sm" aria-label="Small" />
        <span>Small</span>
      </label>
      <label className="flex items-center gap-2 text-sm cursor-pointer">
        <Radio name="size-h" value="md" defaultChecked aria-label="Medium" />
        <span>Medium</span>
      </label>
      <label className="flex items-center gap-2 text-sm cursor-pointer">
        <Radio name="size-h" value="lg" aria-label="Large" />
        <span>Large</span>
      </label>
    </RadioGroup>
  ),
};

export const Disabled: Story = {
  render: () => (
    <RadioGroup>
      <label className="flex items-center gap-2 text-sm cursor-not-allowed opacity-60">
        <Radio name="disabled-group" value="a" disabled aria-label="Option A disabled" />
        <span>Option A (disabled)</span>
      </label>
      <label className="flex items-center gap-2 text-sm cursor-not-allowed opacity-60">
        <Radio name="disabled-group" value="b" disabled defaultChecked aria-label="Option B disabled checked" />
        <span>Option B (disabled, checked)</span>
      </label>
    </RadioGroup>
  ),
};

export const SingleRadio: Story = {
  render: () => (
    <label className="flex items-center gap-2 text-sm cursor-pointer">
      <Radio name="single" value="agree" aria-label="Agree to terms" />
      <span>I agree to the terms and conditions</span>
    </label>
  ),
};
