import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Overlays/Sheet",
  parameters: { layout: "padded" },
};
export default meta;

type Story = StoryObj;

export const RightSide: Story = {
  name: "Side — Right",
  render: () => (
    <div style={{ position: "relative", height: "400px", overflow: "hidden", background: "var(--surface-primary)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-lg)" }}>
      <div className="drawer drawer--right" style={{ position: "absolute", width: "320px" }}>
        <div className="drawer__header">
          <span style={{ fontSize: "var(--font-size-md)", fontWeight: "var(--font-weight-semibold)", color: "var(--text-heading)" }}>Workflow Details</span>
          <button className="btn btn--ghost btn--icon btn--xs" aria-label="Close">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="drawer__body">
          <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)", marginBottom: "var(--space-4)" }}>
            View and edit the details for this workflow.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            <div className="field">
              <label className="field__label">Workflow Name</label>
              <input className="input" type="text" defaultValue="customer-support-triage" />
            </div>
            <div className="field">
              <label className="field__label">Description</label>
              <textarea className="textarea" rows={3} defaultValue="Classifies and routes incoming support tickets." />
            </div>
          </div>
        </div>
      </div>
    </div>
  ),
};

export const BottomSide: Story = {
  name: "Side — Bottom",
  render: () => (
    <div style={{ position: "relative", height: "400px", overflow: "hidden", background: "var(--surface-primary)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-lg)" }}>
      <div className="drawer drawer--bottom" style={{ position: "absolute" }}>
        <div className="drawer__header">
          <span style={{ fontSize: "var(--font-size-md)", fontWeight: "var(--font-weight-semibold)", color: "var(--text-heading)" }}>Bottom Panel</span>
          <button className="btn btn--ghost btn--icon btn--xs" aria-label="Close">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="drawer__body">
          <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-muted)" }}>
            Slides up from the bottom of the screen.
          </p>
        </div>
      </div>
    </div>
  ),
};
