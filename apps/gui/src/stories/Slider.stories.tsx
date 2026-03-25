import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Forms/Slider",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <div style={{ width: "280px" }}>
      <input className="slider" type="range" min={0} max={100} defaultValue={50} aria-label="Volume" />
    </div>
  ),
};

export const WithValue: Story = {
  render: () => {
    const [value, setValue] = React.useState(40);
    return (
      <div style={{ width: "280px", display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "var(--font-size-sm)", color: "var(--text-muted)" }}>
          <span>Temperature</span>
          <span>{value}</span>
        </div>
        <input
          className="slider"
          type="range"
          min={0}
          max={100}
          step={1}
          value={value}
          onChange={(e) => setValue(Number(e.target.value))}
          aria-label="Temperature"
        />
      </div>
    );
  },
};

export const TokenBudget: Story = {
  render: () => {
    const [value, setValue] = React.useState(2048);
    return (
      <div style={{ width: "280px", display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "var(--font-size-sm)", color: "var(--text-primary)" }}>
          <span>Max tokens</span>
          <span style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>{value.toLocaleString()}</span>
        </div>
        <input
          className="slider"
          type="range"
          min={256}
          max={8192}
          step={256}
          value={value}
          onChange={(e) => setValue(Number(e.target.value))}
          aria-label="Max tokens"
        />
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "var(--font-size-xs)", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
          <span>256</span>
          <span>8,192</span>
        </div>
      </div>
    );
  },
};

export const Disabled: Story = {
  render: () => (
    <div style={{ width: "280px" }}>
      <input className="slider" type="range" min={0} max={100} defaultValue={60} disabled aria-label="Disabled slider" />
    </div>
  ),
};
