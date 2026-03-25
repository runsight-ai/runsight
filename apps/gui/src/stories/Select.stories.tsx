import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const meta: Meta = {
  title: "Form Controls/Select",
  parameters: {
    layout: "centered",
  },
};

export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <Select>
      <SelectTrigger className="w-48">
        <SelectValue placeholder="Select a model" />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          <SelectLabel>Anthropic</SelectLabel>
          <SelectItem value="claude-3-5-sonnet">Claude 3.5 Sonnet</SelectItem>
          <SelectItem value="claude-3-opus">Claude 3 Opus</SelectItem>
          <SelectItem value="claude-3-haiku">Claude 3 Haiku</SelectItem>
        </SelectGroup>
        <SelectGroup>
          <SelectLabel>OpenAI</SelectLabel>
          <SelectItem value="gpt-4o">GPT-4o</SelectItem>
          <SelectItem value="gpt-4-turbo">GPT-4 Turbo</SelectItem>
        </SelectGroup>
      </SelectContent>
    </Select>
  ),
};

export const WithValue: Story = {
  render: () => (
    <Select defaultValue="claude-3-5-sonnet">
      <SelectTrigger className="w-48">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="claude-3-5-sonnet">Claude 3.5 Sonnet</SelectItem>
        <SelectItem value="claude-3-opus">Claude 3 Opus</SelectItem>
        <SelectItem value="claude-3-haiku">Claude 3 Haiku</SelectItem>
      </SelectContent>
    </Select>
  ),
};

export const Small: Story = {
  render: () => (
    <Select>
      <SelectTrigger size="sm" className="w-40">
        <SelectValue placeholder="Pick size" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="xs">Extra Small</SelectItem>
        <SelectItem value="sm">Small</SelectItem>
        <SelectItem value="md">Medium</SelectItem>
      </SelectContent>
    </Select>
  ),
};

export const Disabled: Story = {
  render: () => (
    <Select disabled>
      <SelectTrigger className="w-48">
        <SelectValue placeholder="Disabled select" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="option-1">Option 1</SelectItem>
      </SelectContent>
    </Select>
  ),
};
