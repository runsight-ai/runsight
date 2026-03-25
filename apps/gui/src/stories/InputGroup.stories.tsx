import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

// InputGroup composes the .input control with prefix/suffix addons.
// There is no separate .input-group BEM class; we use flex + .input styling.
const meta = {
  title: "Forms/InputGroup",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

const addonStyle: React.CSSProperties = {
  display: "inline-flex", alignItems: "center",
  padding: "0 var(--space-2-5)",
  background: "var(--surface-secondary)",
  border: "1px solid var(--border-default)",
  fontFamily: "var(--font-mono)", fontSize: "var(--font-size-sm)",
  color: "var(--text-muted)", whiteSpace: "nowrap",
  height: "var(--control-height-sm)",
};

export const Default: Story = {
  render: () => (
    <div style={{ width: "288px" }}>
      <input className="input" type="text" placeholder="Enter value" />
    </div>
  ),
};

export const WithPrefix: Story = {
  name: "With Prefix (inline-start addon)",
  render: () => (
    <div style={{ display: "flex", width: "288px" }}>
      <span style={{ ...addonStyle, borderRight: "none", borderRadius: "var(--radius-md) 0 0 var(--radius-md)" }}>$</span>
      <input className="input" type="number" placeholder="0.00" style={{ borderRadius: "0 var(--radius-md) var(--radius-md) 0" }} />
    </div>
  ),
};

export const WithSuffix: Story = {
  name: "With Suffix (inline-end addon)",
  render: () => (
    <div style={{ display: "flex", width: "288px" }}>
      <input className="input" type="number" placeholder="Tokens per second" style={{ borderRadius: "var(--radius-md) 0 0 var(--radius-md)" }} />
      <span style={{ ...addonStyle, borderLeft: "none", borderRadius: "0 var(--radius-md) var(--radius-md) 0" }}>tok/s</span>
    </div>
  ),
};

export const WithPrefixAndSuffix: Story = {
  name: "With Prefix and Suffix",
  render: () => (
    <div style={{ display: "flex", width: "288px" }}>
      <span style={{ ...addonStyle, borderRight: "none", borderRadius: "var(--radius-md) 0 0 var(--radius-md)" }}>https://</span>
      <input className="input" type="text" placeholder="api.example.com" style={{ borderRadius: 0, borderLeft: "none", borderRight: "none" }} />
      <span style={{ ...addonStyle, borderLeft: "none", borderRadius: "0 var(--radius-md) var(--radius-md) 0" }}>/v1</span>
    </div>
  ),
};

export const Disabled: Story = {
  render: () => (
    <div style={{ display: "flex", width: "288px" }}>
      <span style={{ ...addonStyle, borderRight: "none", borderRadius: "var(--radius-md) 0 0 var(--radius-md)", opacity: 0.5 }}>@</span>
      <input className="input input--disabled" type="text" placeholder="username" disabled style={{ borderRadius: "0 var(--radius-md) var(--radius-md) 0" }} />
    </div>
  ),
};
