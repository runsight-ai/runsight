import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Primitives/Skeleton",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

export const Default: Story = {
  name: "Default — all variants",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)", padding: "var(--space-6)", width: "320px", background: "var(--surface-primary)", borderRadius: "var(--radius-lg)" }}>
      <div className="skeleton skeleton--heading" />
      <div className="skeleton skeleton--text" />
      <div className="skeleton skeleton--text" />
      <div className="skeleton skeleton--text-sm" />
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", marginTop: "var(--space-2)" }}>
        <div className="skeleton skeleton--avatar" />
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
          <div className="skeleton skeleton--text" />
          <div className="skeleton skeleton--text-sm" />
        </div>
      </div>
      <div className="skeleton skeleton--button" />
    </div>
  ),
};

export const Individual: Story = {
  name: "Individual variants",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)", padding: "var(--space-6)", width: "320px" }}>
      <div>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: "var(--font-size-2xs)", color: "var(--text-muted)", marginBottom: "var(--space-2)", textTransform: "uppercase", letterSpacing: "var(--tracking-wide)" }}>heading (18px × 40%)</div>
        <div className="skeleton skeleton--heading" />
      </div>
      <div>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: "var(--font-size-2xs)", color: "var(--text-muted)", marginBottom: "var(--space-2)", textTransform: "uppercase", letterSpacing: "var(--tracking-wide)" }}>text (14px × 80%)</div>
        <div className="skeleton skeleton--text" />
      </div>
      <div>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: "var(--font-size-2xs)", color: "var(--text-muted)", marginBottom: "var(--space-2)", textTransform: "uppercase", letterSpacing: "var(--tracking-wide)" }}>text-sm (13px × 60%)</div>
        <div className="skeleton skeleton--text-sm" />
      </div>
      <div>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: "var(--font-size-2xs)", color: "var(--text-muted)", marginBottom: "var(--space-2)", textTransform: "uppercase", letterSpacing: "var(--tracking-wide)" }}>avatar (32×32)</div>
        <div className="skeleton skeleton--avatar" />
      </div>
      <div>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: "var(--font-size-2xs)", color: "var(--text-muted)", marginBottom: "var(--space-2)", textTransform: "uppercase", letterSpacing: "var(--tracking-wide)" }}>button (32×100)</div>
        <div className="skeleton skeleton--button" />
      </div>
    </div>
  ),
};
