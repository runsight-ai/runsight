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

export const NumberSpinner: Story = {
  name: "Number Spinner (up/down buttons)",
  render: () => (
    <div style={{ display: "flex", width: "160px" }}>
      <input
        className="input"
        type="number"
        defaultValue={4}
        min={1}
        max={32}
        style={{ borderRadius: "var(--radius-md) 0 0 var(--radius-md)", borderRight: "none", flex: 1 }}
      />
      <div style={{ display: "flex", flexDirection: "column", borderTop: "1px solid var(--border-default)", borderRight: "1px solid var(--border-default)", borderBottom: "1px solid var(--border-default)", borderRadius: "0 var(--radius-md) var(--radius-md) 0", overflow: "hidden" }}>
        <button
          className="btn btn--ghost btn--icon btn--xs"
          aria-label="Increment"
          style={{ borderRadius: 0, height: "50%", minHeight: "unset", flex: 1, borderBottom: "1px solid var(--border-subtle)" }}
        >
          <span className="icon icon--md">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 15l7-7 7 7" />
            </svg>
          </span>
        </button>
        <button
          className="btn btn--ghost btn--icon btn--xs"
          aria-label="Decrement"
          style={{ borderRadius: 0, height: "50%", minHeight: "unset", flex: 1 }}
        >
          <span className="icon icon--md">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 9l-7 7-7-7" />
            </svg>
          </span>
        </button>
      </div>
    </div>
  ),
};
