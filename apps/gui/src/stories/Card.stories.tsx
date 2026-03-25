import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Data Display/Card",
  parameters: { layout: "padded" },
};
export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <div className="card" style={{ maxWidth: "360px" }}>
      <div className="card__body">
        <p style={{ fontSize: "var(--font-size-md)", color: "var(--text-primary)" }}>
          A simple card with content and no header.
        </p>
      </div>
    </div>
  ),
};

export const WithHeader: Story = {
  name: "With Header",
  render: () => (
    <div className="card" style={{ maxWidth: "360px" }}>
      <div className="card__header">
        <div>
          <div style={{ fontSize: "var(--font-size-md)", fontWeight: "var(--font-weight-semibold)", color: "var(--text-heading)" }}>
            Active Workflows
          </div>
          <div style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)", marginTop: "var(--space-0-5)" }}>
            Workflows currently running in your workspace.
          </div>
        </div>
      </div>
      <div className="card__body">
        <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>
          12 workflows are currently active.
        </p>
      </div>
    </div>
  ),
};

export const WithHeaderAndAction: Story = {
  name: "With Header and Action",
  render: () => (
    <div className="card" style={{ maxWidth: "360px" }}>
      <div className="card__header">
        <div>
          <div style={{ fontSize: "var(--font-size-md)", fontWeight: "var(--font-weight-semibold)", color: "var(--text-heading)" }}>
            Workflow Overview
          </div>
          <div style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)", marginTop: "var(--space-0-5)" }}>
            Summary of your most recent runs.
          </div>
        </div>
        <button className="btn btn--ghost btn--xs">View all</button>
      </div>
      <div className="card__body">
        <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>
          3 completed, 1 running, 0 failed.
        </p>
      </div>
      <div className="card__footer">
        <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>Updated 2 min ago</span>
      </div>
    </div>
  ),
};

export const Raised: Story = {
  name: "Raised",
  render: () => (
    <div className="card card--raised" style={{ maxWidth: "360px" }}>
      <div className="card__header">
        <div style={{ fontSize: "var(--font-size-md)", fontWeight: "var(--font-weight-semibold)", color: "var(--text-heading)" }}>
          Raised Card
        </div>
      </div>
      <div className="card__body">
        <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>
          Elevated surface with subtle shadow lift.
        </p>
      </div>
    </div>
  ),
};

export const Interactive: Story = {
  name: "Interactive",
  render: () => (
    <div className="card card--interactive" style={{ maxWidth: "360px" }} tabIndex={0}>
      <div className="card__header">
        <div style={{ fontSize: "var(--font-size-md)", fontWeight: "var(--font-weight-semibold)", color: "var(--text-heading)" }}>
          Clickable Card
        </div>
      </div>
      <div className="card__body">
        <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>
          Hover to see the interactive state.
        </p>
      </div>
    </div>
  ),
};
