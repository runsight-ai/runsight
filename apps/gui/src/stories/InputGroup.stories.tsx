import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
  InputGroupText,
} from "@/components/ui/input-group";

const meta: Meta = {
  title: "Form Controls/InputGroup",
  parameters: {
    layout: "centered",
  },
};

export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <InputGroup className="w-72">
      <InputGroupInput placeholder="Enter value" />
    </InputGroup>
  ),
};

export const WithPrefix: Story = {
  name: "With Prefix (inline-start addon)",
  render: () => (
    <InputGroup className="w-72">
      <InputGroupAddon align="inline-start">
        <InputGroupText>$</InputGroupText>
      </InputGroupAddon>
      <InputGroupInput placeholder="0.00" type="number" />
    </InputGroup>
  ),
};

export const WithSuffix: Story = {
  name: "With Suffix (inline-end addon)",
  render: () => (
    <InputGroup className="w-72">
      <InputGroupInput placeholder="Tokens per second" type="number" />
      <InputGroupAddon align="inline-end">
        <InputGroupText>tok/s</InputGroupText>
      </InputGroupAddon>
    </InputGroup>
  ),
};

export const WithPrefixAndSuffix: Story = {
  name: "With Prefix and Suffix",
  render: () => (
    <InputGroup className="w-72">
      <InputGroupAddon align="inline-start">
        <InputGroupText>https://</InputGroupText>
      </InputGroupAddon>
      <InputGroupInput placeholder="api.example.com" />
      <InputGroupAddon align="inline-end">
        <InputGroupText>/v1</InputGroupText>
      </InputGroupAddon>
    </InputGroup>
  ),
};

export const Disabled: Story = {
  render: () => (
    <InputGroup className="w-72">
      <InputGroupAddon align="inline-start">
        <InputGroupText>@</InputGroupText>
      </InputGroupAddon>
      <InputGroupInput placeholder="username" disabled />
    </InputGroup>
  ),
};
