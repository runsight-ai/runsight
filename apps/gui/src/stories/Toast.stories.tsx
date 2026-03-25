import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Primitives/Toast",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

export const Success: Story = {
  name: "Variant: success",
  render: () => (
    <div className="toast toast--success" style={{ minWidth: "320px" }}>
      <div className="toast__icon">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
          <path d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
      <div className="toast__content">
        <div className="toast__title">Workflow saved</div>
        <div className="toast__description">Your workflow has been saved successfully.</div>
      </div>
    </div>
  ),
};

export const Danger: Story = {
  name: "Variant: danger",
  render: () => (
    <div className="toast toast--danger" style={{ minWidth: "320px" }}>
      <div className="toast__icon">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
        </svg>
      </div>
      <div className="toast__content">
        <div className="toast__title">Execution failed</div>
        <div className="toast__description">Step 3 encountered an unrecoverable error.</div>
      </div>
    </div>
  ),
};

export const Warning: Story = {
  name: "Variant: warning",
  render: () => (
    <div className="toast toast--warning" style={{ minWidth: "320px" }}>
      <div className="toast__icon">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
        </svg>
      </div>
      <div className="toast__content">
        <div className="toast__title">Token limit approaching</div>
        <div className="toast__description">This workflow is consuming tokens faster than expected.</div>
      </div>
    </div>
  ),
};

export const Info: Story = {
  name: "Variant: info",
  render: () => (
    <div className="toast toast--info" style={{ minWidth: "320px" }}>
      <div className="toast__icon">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
          <path d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
        </svg>
      </div>
      <div className="toast__content">
        <div className="toast__title">Workflow queued</div>
        <div className="toast__description">Your workflow has been added to the execution queue.</div>
      </div>
    </div>
  ),
};

export const WithDismiss: Story = {
  name: "With Dismiss Button",
  render: () => (
    <div className="toast toast--info" style={{ minWidth: "320px" }}>
      <div className="toast__content">
        <div className="toast__title">New update available</div>
        <div className="toast__description">Runsight v1.2 is ready to install.</div>
      </div>
      <button className="toast__dismiss btn btn--ghost btn--icon btn--xs" aria-label="Dismiss">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
          <path d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  ),
};

export const AllVariants: Story = {
  name: "All Variants",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", width: "360px" }}>
      <div className="toast toast--success">
        <div className="toast__content">
          <div className="toast__title">Workflow saved</div>
          <div className="toast__description">Changes saved successfully.</div>
        </div>
      </div>
      <div className="toast toast--danger">
        <div className="toast__content">
          <div className="toast__title">Execution failed</div>
          <div className="toast__description">An error occurred during execution.</div>
        </div>
      </div>
      <div className="toast toast--warning">
        <div className="toast__content">
          <div className="toast__title">Rate limit warning</div>
          <div className="toast__description">Approaching API rate limit.</div>
        </div>
      </div>
      <div className="toast toast--info">
        <div className="toast__content">
          <div className="toast__title">Workflow queued</div>
          <div className="toast__description">Processing will begin shortly.</div>
        </div>
      </div>
    </div>
  ),
};
