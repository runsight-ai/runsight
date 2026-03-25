import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { Textarea } from "@/components/ui/textarea";

const meta: Meta<typeof Textarea> = {
  title: "Primitives/Textarea",
  component: Textarea,
  parameters: {
    layout: "centered",
  },
  argTypes: {
    disabled: { control: "boolean" },
    placeholder: { control: "text" },
    rows: { control: "number" },
  },
};

export default meta;

type Story = StoryObj<typeof Textarea>;

export const Default: Story = {
  args: {
    placeholder: "Enter a description...",
    rows: 4,
  },
};

export const WithValue: Story = {
  args: {
    defaultValue: "You are a helpful AI assistant that routes customer support tickets based on their content and urgency.",
    rows: 4,
  },
};

export const Disabled: Story = {
  args: {
    placeholder: "Disabled textarea",
    disabled: true,
    rows: 3,
  },
};

export const Error: Story = {
  args: {
    defaultValue: "Invalid prompt content",
    "aria-invalid": true,
    rows: 3,
  },
};

export const CodeVariant: Story = {
  name: "Code Variant",
  args: {
    placeholder: "// Enter your code here",
    rows: 6,
    className: "font-mono",
  },
};
