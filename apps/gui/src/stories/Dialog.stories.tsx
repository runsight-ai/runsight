import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Overlays/Dialog",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <div style={{ position: "relative", width: "480px" }}>
      <div className="modal modal--md" style={{ position: "static", transform: "none", background: "var(--elevation-overlay-surface)", border: "1px solid var(--elevation-border-raised)" }}>
        <div className="modal__header">
          <span className="modal__title">Workflow Settings</span>
          <button className="btn btn--ghost btn--icon btn--xs" aria-label="Close">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="modal__body">
          <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>
            Configure settings for this workflow. Changes are saved automatically.
          </p>
        </div>
      </div>
    </div>
  ),
};

export const WithFormAndFooter: Story = {
  name: "With Form and Footer",
  render: () => (
    <div style={{ width: "480px" }}>
      <div className="modal modal--md" style={{ position: "static", transform: "none", background: "var(--elevation-overlay-surface)", border: "1px solid var(--elevation-border-raised)" }}>
        <div className="modal__header">
          <span className="modal__title">Edit Soul</span>
          <button className="btn btn--ghost btn--icon btn--xs" aria-label="Close">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="modal__body">
          <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)", marginBottom: "var(--space-4)" }}>
            Update the identity and prompt for this agent soul.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            <div className="field">
              <label className="field__label">Name</label>
              <input className="input" type="text" defaultValue="Planner Soul" />
            </div>
            <div className="field">
              <label className="field__label">Model</label>
              <input className="input" type="text" defaultValue="claude-3-5-sonnet" />
            </div>
          </div>
        </div>
        <div className="modal__footer">
          <button className="btn btn--secondary btn--sm">Cancel</button>
          <button className="btn btn--primary btn--sm">Save Changes</button>
        </div>
      </div>
    </div>
  ),
};

export const Destructive: Story = {
  render: () => (
    <div style={{ width: "480px" }}>
      <div className="modal modal--sm" style={{ position: "static", transform: "none", background: "var(--elevation-overlay-surface)", border: "1px solid var(--elevation-border-raised)" }}>
        <div className="modal__header">
          <span className="modal__title">Delete Workflow</span>
        </div>
        <div className="modal__body">
          <p style={{ fontSize: "var(--font-size-md)", color: "var(--text-secondary)" }}>
            This action cannot be undone. The workflow and all its run history will be permanently removed.
          </p>
        </div>
        <div className="modal__footer">
          <button className="btn btn--secondary btn--sm">Cancel</button>
          <button className="btn btn--danger btn--sm">Delete</button>
        </div>
      </div>
    </div>
  ),
};
