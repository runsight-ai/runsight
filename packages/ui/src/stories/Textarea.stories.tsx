import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { Textarea } from "../components/ui/textarea";

const meta: Meta<typeof Textarea> = {
  title: "Forms/Textarea",
  component: Textarea,
  parameters: { layout: "centered" },
  argTypes: {
    code: { control: "boolean" },
    autoResize: { control: "boolean" },
    disabled: { control: "boolean" },
    placeholder: { control: "text" },
    rows: { control: { type: "number", min: 2, max: 20 } },
  },
  decorators: [
    (Story) => (
      <div style={{ width: "320px" }}>
        <Story />
      </div>
    ),
  ],
};
export default meta;

type Story = StoryObj<typeof Textarea>;

export const Default: Story = {
  name: "Default (controls)",
  args: {
    placeholder: "Enter a description…",
    rows: 4,
    code: false,
    autoResize: false,
    disabled: false,
  },
};

export const CodeVariant: Story = {
  name: "Code Variant",
  args: {
    code: true,
    rows: 6,
    placeholder: "# Enter YAML here…",
  },
};

export const Disabled: Story = {
  name: "Disabled",
  args: {
    placeholder: "Disabled textarea",
    rows: 3,
    disabled: true,
  },
};

export const WithLabel: Story = {
  name: "With Label",
  render: () => (
    <div className="field">
      <label className="field__label" htmlFor="system-prompt">System Prompt</label>
      <Textarea
        id="system-prompt"
        rows={4}
        placeholder="You are a helpful assistant…"
      />
      <span className="field__helper">
        This prompt is injected at the start of every conversation.
      </span>
    </div>
  ),
};
