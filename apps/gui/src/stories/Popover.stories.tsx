import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Overlays/Popover",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <div style={{ position: "relative", display: "inline-block", padding: "var(--space-8)" }}>
      <button className="btn btn--secondary">Open Popover</button>
      <div className="popover" style={{ position: "absolute", top: "calc(100% + var(--space-2))", left: 0, minWidth: "240px" }}>
        <div style={{ marginBottom: "var(--space-2)" }}>
          <div style={{ fontSize: "var(--font-size-md)", fontWeight: "var(--font-weight-semibold)", color: "var(--text-heading)" }}>Soul Configuration</div>
          <div style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)", marginTop: "var(--space-0-5)" }}>Adjust the active soul for this step.</div>
        </div>
        <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-muted)" }}>
          Select a soul from the list or create a new one.
        </p>
      </div>
    </div>
  ),
};

export const WithFormContent: Story = {
  name: "With Form Content",
  render: () => (
    <div style={{ position: "relative", display: "inline-block", padding: "var(--space-8)" }}>
      <button className="btn btn--secondary">Filter Results</button>
      <div className="popover" style={{ position: "absolute", top: "calc(100% + var(--space-2))", left: 0, minWidth: "260px" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
          <div className="field">
            <label className="field__label">Status</label>
            <select className="select">
              <option value="">All statuses</option>
              <option value="running">Running</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
            </select>
          </div>
          <div className="field">
            <label className="field__label">Model</label>
            <select className="select">
              <option value="">All models</option>
              <option value="sonnet">Claude Sonnet</option>
              <option value="opus">Claude Opus</option>
            </select>
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}>
            <button className="btn btn--ghost btn--sm">Reset</button>
            <button className="btn btn--primary btn--sm">Apply</button>
          </div>
        </div>
      </div>
    </div>
  ),
};
