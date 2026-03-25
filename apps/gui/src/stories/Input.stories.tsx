import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const meta: Meta<typeof Input> = {
  title: "Forms/Input",
  component: Input,
  parameters: { layout: "centered" },
  argTypes: {
    size: {
      control: { type: "select" },
      options: [undefined, "xs", "md", "lg"],
      labels: { undefined: "sm (default)" },
    },
    error: { control: "boolean" },
    disabled: { control: "boolean" },
    placeholder: { control: "text" },
  },
  decorators: [
    (Story) => (
      <div style={{ width: "280px" }}>
        <Story />
      </div>
    ),
  ],
};
export default meta;

type Story = StoryObj<typeof Input>;

export const Default: Story = {
  name: "Default (controls)",
  args: {
    placeholder: "Workflow name…",
    size: undefined,
    error: false,
    disabled: false,
  },
};

export const WithLabel: Story = {
  name: "With Label",
  render: () => (
    <div className="field">
      <Label htmlFor="soul-name">Soul Name</Label>
      <Input id="soul-name" type="text" placeholder="e.g. analyst-soul" />
    </div>
  ),
};

export const WithHelperText: Story = {
  name: "With Helper Text",
  render: () => (
    <div className="field">
      <Label htmlFor="soul-name-helper">Soul Name</Label>
      <Input id="soul-name-helper" type="text" placeholder="e.g. analyst-soul" />
      <span className="field__helper">Used to identify this soul in YAML definitions.</span>
    </div>
  ),
};

export const WithError: Story = {
  name: "With Error",
  render: () => (
    <div className="field">
      <Label htmlFor="error-field">Webhook URL</Label>
      <Input id="error-field" type="text" defaultValue="not-a-valid-url" error />
      <span className="field__error">Must be a valid URL</span>
    </div>
  ),
};

export const Error: Story = {
  name: "Error State",
  render: () => (
    <div className="field">
      <Label htmlFor="error-field-2">Invalid Field</Label>
      <Input id="error-field-2" type="text" defaultValue="not-a-valid-url" error />
      <span className="field__error">Must be a valid URL</span>
    </div>
  ),
};

export const Disabled: Story = {
  name: "Disabled",
  args: {
    placeholder: "Disabled field",
    disabled: true,
  },
};

export const Sizes: Story = {
  name: "All Sizes",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <Input size="xs" type="text" placeholder="XS input" />
      <Input type="text" placeholder="SM (default)" />
      <Input size="md" type="text" placeholder="MD input" />
      <Input size="lg" type="text" placeholder="LG input" />
    </div>
  ),
};
