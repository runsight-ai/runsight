import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { Input } from "@/components/ui/input";

const meta: Meta<typeof Input> = {
  title: "Primitives/Input",
  component: Input,
  parameters: {
    layout: "centered",
  },
  argTypes: {
    disabled: { control: "boolean" },
    placeholder: { control: "text" },
  },
};

export default meta;

type Story = StoryObj<typeof Input>;

export const Default: Story = {
  args: {
    placeholder: "Workflow name",
    type: "text",
  },
};

export const WithValue: Story = {
  args: {
    defaultValue: "customer-support-triage",
    type: "text",
  },
};

export const Disabled: Story = {
  args: {
    placeholder: "Disabled input",
    disabled: true,
    type: "text",
  },
};

export const Error: Story = {
  args: {
    defaultValue: "bad-value",
    "aria-invalid": true,
    type: "text",
  },
};

export const Password: Story = {
  args: {
    placeholder: "Enter password",
    type: "password",
  },
};

export const Search: Story = {
  args: {
    placeholder: "Search workflows...",
    type: "search",
  },
};
