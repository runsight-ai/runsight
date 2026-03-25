import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Navigation/Tabs",
  parameters: { layout: "padded" },
};
export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <div style={{ width: "400px" }}>
      <div className="tabs">
        <button className="tab" aria-selected="true" role="tab">Overview</button>
        <button className="tab" aria-selected="false" role="tab">Runs</button>
        <button className="tab" aria-selected="false" role="tab">Settings</button>
      </div>
      <div style={{ paddingTop: "var(--space-4)", fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>
        Overview content
      </div>
    </div>
  ),
};

export const LineUnderline: Story = {
  name: "Line (Underline Indicator)",
  render: () => (
    <div style={{ width: "400px" }}>
      <div className="tabs">
        <button className="tab" aria-selected="true" role="tab">Workflows</button>
        <button className="tab" aria-selected="false" role="tab">Souls</button>
        <button className="tab" aria-selected="false" role="tab">Steps</button>
        <button className="tab" aria-selected="false" role="tab">Runs</button>
      </div>
      <div style={{ paddingTop: "var(--space-4)", fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>
        Workflows list
      </div>
    </div>
  ),
};

export const Contained: Story = {
  name: "Contained (Pill Style)",
  render: () => (
    <div style={{ width: "400px" }}>
      <div className="tabs tabs--contained">
        <button className="tab" aria-selected="true" role="tab">Overview</button>
        <button className="tab" aria-selected="false" role="tab">Runs</button>
        <button className="tab" aria-selected="false" role="tab">Settings</button>
      </div>
    </div>
  ),
};

export const WithBadge: Story = {
  name: "With Badge Count",
  render: () => (
    <div style={{ width: "400px" }}>
      <div className="tabs">
        <button className="tab" aria-selected="true" role="tab">
          Runs
          <span className="tab__badge">24</span>
        </button>
        <button className="tab" aria-selected="false" role="tab">
          Errors
          <span className="tab__badge">3</span>
        </button>
        <button className="tab" aria-selected="false" role="tab">Settings</button>
      </div>
    </div>
  ),
};

export const Disabled: Story = {
  render: () => (
    <div style={{ width: "400px" }}>
      <div className="tabs">
        <button className="tab" aria-selected="true" role="tab">Active</button>
        <button className="tab" aria-selected="false" role="tab" disabled style={{ opacity: 0.4, cursor: "not-allowed" }}>Disabled</button>
        <button className="tab" aria-selected="false" role="tab">Another</button>
      </div>
      <div style={{ paddingTop: "var(--space-4)", fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>
        Active tab content
      </div>
    </div>
  ),
};
