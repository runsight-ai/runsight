import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Forms/Input",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <div style={{ width: "280px" }}>
      <input className="input" type="text" placeholder="Workflow name…" />
    </div>
  ),
};

export const WithValue: Story = {
  render: () => (
    <div style={{ width: "280px" }}>
      <input className="input" type="text" defaultValue="research-pipeline-v2" />
    </div>
  ),
};

export const Error: Story = {
  render: () => (
    <div style={{ width: "280px", display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
      <input className="input input--error" type="text" defaultValue="invalid-name!" />
      <span style={{ fontSize: "var(--font-size-xs)", color: "var(--danger-11)" }}>Name may only contain letters, numbers, and hyphens.</span>
    </div>
  ),
};

export const Disabled: Story = {
  render: () => (
    <div style={{ width: "280px" }}>
      <input className="input input--disabled" type="text" placeholder="Disabled field" disabled />
    </div>
  ),
};

export const Readonly: Story = {
  render: () => (
    <div style={{ width: "280px" }}>
      <input className="input input--readonly" type="text" defaultValue="readonly-value" readOnly />
    </div>
  ),
};

export const Password: Story = {
  render: () => (
    <div style={{ width: "280px" }}>
      <input className="input" type="password" placeholder="Enter API key…" />
    </div>
  ),
};

export const Search: Story = {
  render: () => (
    <div style={{ width: "280px" }}>
      <input className="input" type="search" placeholder="Search workflows…" />
    </div>
  ),
};

export const Sizes: Story = {
  render: () => (
    <div style={{ width: "280px", display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <input className="input input--xs" type="text" placeholder="XS input" />
      <input className="input" type="text" placeholder="SM (default)" />
      <input className="input input--md" type="text" placeholder="MD input" />
      <input className="input input--lg" type="text" placeholder="LG input" />
    </div>
  ),
};

export const WithLabel: Story = {
  render: () => (
    <div className="field" style={{ width: "280px" }}>
      <label className="field__label">Soul Name</label>
      <input className="input" type="text" placeholder="e.g. analyst-soul" />
      <span className="field__helper">Used to identify this soul in YAML definitions.</span>
    </div>
  ),
};
