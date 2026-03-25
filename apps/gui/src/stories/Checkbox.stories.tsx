import type { Meta, StoryObj } from "@storybook/react";
import React, { useRef, useEffect } from "react";

const meta = {
  title: "Forms/Checkbox",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <label className="checkbox">
      <input className="checkbox__input" type="checkbox" />
      <span className="checkbox__label">Accept terms</span>
    </label>
  ),
};

export const Checked: Story = {
  render: () => (
    <label className="checkbox">
      <input className="checkbox__input" type="checkbox" defaultChecked />
      <span className="checkbox__label">Checked</span>
    </label>
  ),
};

export const Indeterminate: Story = {
  render: () => {
    const IndeterminateBox = () => {
      const ref = useRef<HTMLInputElement>(null);
      useEffect(() => {
        if (ref.current) ref.current.indeterminate = true;
      }, []);
      return (
        <label className="checkbox">
          <input className="checkbox__input" type="checkbox" ref={ref} />
          <span className="checkbox__label">Indeterminate</span>
        </label>
      );
    };
    return <IndeterminateBox />;
  },
};

export const Disabled: Story = {
  render: () => (
    <label className="checkbox">
      <input className="checkbox__input" type="checkbox" disabled />
      <span className="checkbox__label">Disabled</span>
    </label>
  ),
};

export const DisabledChecked: Story = {
  name: "Disabled (Checked)",
  render: () => (
    <label className="checkbox">
      <input className="checkbox__input" type="checkbox" disabled defaultChecked />
      <span className="checkbox__label">Disabled (checked)</span>
    </label>
  ),
};

export const AllStates: Story = {
  render: () => {
    const IndeterminateBox = () => {
      const ref = useRef<HTMLInputElement>(null);
      useEffect(() => {
        if (ref.current) ref.current.indeterminate = true;
      }, []);
      return (
        <label className="checkbox">
          <input className="checkbox__input" type="checkbox" ref={ref} />
          <span className="checkbox__label">Indeterminate</span>
        </label>
      );
    };
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
        <label className="checkbox">
          <input className="checkbox__input" type="checkbox" />
          <span className="checkbox__label">Unchecked</span>
        </label>
        <label className="checkbox">
          <input className="checkbox__input" type="checkbox" defaultChecked />
          <span className="checkbox__label">Checked</span>
        </label>
        <IndeterminateBox />
        <label className="checkbox">
          <input className="checkbox__input" type="checkbox" disabled />
          <span className="checkbox__label">Disabled</span>
        </label>
      </div>
    );
  },
};
