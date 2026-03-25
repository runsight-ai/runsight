import type { Meta, StoryObj } from "@storybook/react";
import React, { useRef, useEffect } from "react";

import { Checkbox } from "@/components/ui/checkbox";

const meta: Meta<typeof Checkbox> = {
  title: "Form Controls/Checkbox",
  component: Checkbox,
  parameters: {
    layout: "centered",
  },
  argTypes: {
    disabled: { control: "boolean" },
    indeterminate: { control: "boolean" },
  },
};

export default meta;

type Story = StoryObj<typeof Checkbox>;

export const Default: Story = {
  args: {
    "aria-label": "Accept terms",
  },
};

export const Checked: Story = {
  args: {
    defaultChecked: true,
    "aria-label": "Checked checkbox",
  },
};

export const Unchecked: Story = {
  args: {
    defaultChecked: false,
    "aria-label": "Unchecked checkbox",
  },
};

export const Indeterminate: Story = {
  render: () => {
    const ref = useRef<HTMLInputElement>(null);
    useEffect(() => {
      if (ref.current) {
        ref.current.indeterminate = true;
      }
    }, []);
    return <Checkbox ref={ref} aria-label="Indeterminate checkbox" />;
  },
};

export const Disabled: Story = {
  args: {
    disabled: true,
    "aria-label": "Disabled checkbox",
  },
};

export const DisabledChecked: Story = {
  name: "Disabled (Checked)",
  args: {
    disabled: true,
    defaultChecked: true,
    "aria-label": "Disabled and checked checkbox",
  },
};

export const WithLabel: Story = {
  render: () => (
    <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
      <Checkbox defaultChecked aria-label="Enable notifications" />
      <span>Enable email notifications</span>
    </label>
  ),
};

export const AllStates: Story = {
  render: () => {
    const IndeterminateCheckbox = () => {
      const ref = useRef<HTMLInputElement>(null);
      useEffect(() => {
        if (ref.current) ref.current.indeterminate = true;
      }, []);
      return <Checkbox ref={ref} aria-label="Indeterminate" />;
    };

    return (
      <div className="flex flex-col gap-3">
        <label className="flex items-center gap-2 text-sm">
          <Checkbox aria-label="Unchecked" />
          <span>Unchecked</span>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <Checkbox defaultChecked aria-label="Checked" />
          <span>Checked</span>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <IndeterminateCheckbox />
          <span>Indeterminate</span>
        </label>
        <label className="flex items-center gap-2 text-sm opacity-60">
          <Checkbox disabled aria-label="Disabled" />
          <span>Disabled</span>
        </label>
      </div>
    );
  },
};
