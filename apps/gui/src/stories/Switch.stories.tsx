import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Forms/Switch",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <label className="switch">
      <input className="switch__input" type="checkbox" />
      <span className="switch__track">
        <span className="switch__thumb" />
      </span>
      <span className="switch__label">Enable feature</span>
    </label>
  ),
};

export const On: Story = {
  render: () => (
    <label className="switch">
      <input className="switch__input" type="checkbox" defaultChecked />
      <span className="switch__track">
        <span className="switch__thumb" />
      </span>
      <span className="switch__label">Enabled</span>
    </label>
  ),
};

export const Off: Story = {
  render: () => (
    <label className="switch">
      <input className="switch__input" type="checkbox" />
      <span className="switch__track">
        <span className="switch__thumb" />
      </span>
      <span className="switch__label">Disabled</span>
    </label>
  ),
};

export const Disabled: Story = {
  render: () => (
    <label className="switch">
      <input className="switch__input" type="checkbox" disabled />
      <span className="switch__track">
        <span className="switch__thumb" />
      </span>
      <span className="switch__label">Unavailable</span>
    </label>
  ),
};

export const AllStates: Story = {
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <label className="switch">
        <input className="switch__input" type="checkbox" />
        <span className="switch__track"><span className="switch__thumb" /></span>
        <span className="switch__label">Off</span>
      </label>
      <label className="switch">
        <input className="switch__input" type="checkbox" defaultChecked />
        <span className="switch__track"><span className="switch__thumb" /></span>
        <span className="switch__label">On</span>
      </label>
      <label className="switch">
        <input className="switch__input" type="checkbox" disabled />
        <span className="switch__track"><span className="switch__thumb" /></span>
        <span className="switch__label">Disabled Off</span>
      </label>
      <label className="switch">
        <input className="switch__input" type="checkbox" disabled defaultChecked />
        <span className="switch__track"><span className="switch__thumb" /></span>
        <span className="switch__label">Disabled On</span>
      </label>
    </div>
  ),
};
