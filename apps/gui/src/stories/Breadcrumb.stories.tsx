import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Navigation/Breadcrumb",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <nav className="breadcrumb" aria-label="Breadcrumb">
      <a className="breadcrumb__item" href="#">Home</a>
      <span className="breadcrumb__separator">/</span>
      <span className="breadcrumb__item" aria-current="page">Workflows</span>
    </nav>
  ),
};

export const Basic: Story = {
  render: () => (
    <nav className="breadcrumb" aria-label="Breadcrumb">
      <a className="breadcrumb__item" href="#">Home</a>
      <span className="breadcrumb__separator">/</span>
      <a className="breadcrumb__item" href="#">Workflows</a>
      <span className="breadcrumb__separator">/</span>
      <span className="breadcrumb__item" aria-current="page">Agent Pipeline</span>
    </nav>
  ),
};

export const DeepNesting: Story = {
  name: "Deep Nesting",
  render: () => (
    <nav className="breadcrumb" aria-label="Breadcrumb">
      <a className="breadcrumb__item" href="#">Home</a>
      <span className="breadcrumb__separator">/</span>
      <a className="breadcrumb__item" href="#">Workflows</a>
      <span className="breadcrumb__separator">/</span>
      <a className="breadcrumb__item" href="#">Agent Pipeline</a>
      <span className="breadcrumb__separator">/</span>
      <a className="breadcrumb__item" href="#">Steps</a>
      <span className="breadcrumb__separator">/</span>
      <span className="breadcrumb__item" aria-current="page">Research Step</span>
    </nav>
  ),
};

export const WithMonoId: Story = {
  name: "With Mono ID Segment",
  render: () => (
    <nav className="breadcrumb" aria-label="Breadcrumb">
      <a className="breadcrumb__item" href="#">Workflows</a>
      <span className="breadcrumb__separator">/</span>
      <a className="breadcrumb__item" href="#">Agent Pipeline</a>
      <span className="breadcrumb__separator">/</span>
      <a className="breadcrumb__item breadcrumb__item--id" href="#">run_8f3k2m</a>
      <span className="breadcrumb__separator">/</span>
      <span className="breadcrumb__item" aria-current="page">Logs</span>
    </nav>
  ),
};

export const MultiLevel: Story = {
  name: "Multi Level Navigation",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <nav className="breadcrumb" aria-label="Level 1">
        <a className="breadcrumb__item" href="#">Home</a>
        <span className="breadcrumb__separator">/</span>
        <span className="breadcrumb__item" aria-current="page">Level 1</span>
      </nav>
      <nav className="breadcrumb" aria-label="Level 2">
        <a className="breadcrumb__item" href="#">Home</a>
        <span className="breadcrumb__separator">/</span>
        <a className="breadcrumb__item" href="#">Level 1</a>
        <span className="breadcrumb__separator">/</span>
        <span className="breadcrumb__item" aria-current="page">Level 2</span>
      </nav>
      <nav className="breadcrumb" aria-label="Level 3">
        <a className="breadcrumb__item" href="#">Home</a>
        <span className="breadcrumb__separator">/</span>
        <a className="breadcrumb__item" href="#">Level 1</a>
        <span className="breadcrumb__separator">/</span>
        <a className="breadcrumb__item" href="#">Level 2</a>
        <span className="breadcrumb__separator">/</span>
        <span className="breadcrumb__item" aria-current="page">Level 3</span>
      </nav>
    </div>
  ),
};
