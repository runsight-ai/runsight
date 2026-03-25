import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Data Display/StatCard",
  parameters: { layout: "padded" },
};
export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <div className="stat-card" style={{ width: "200px" }}>
      <div className="stat-card__label">Active Workflows</div>
      <div className="stat-card__value">12</div>
    </div>
  ),
};

export const WithTrendUp: Story = {
  name: "With Trend Up",
  render: () => (
    <div className="stat-card stat-card--accent" style={{ width: "200px" }}>
      <div className="stat-card__label">Completed Runs</div>
      <div className="stat-card__value">4,820</div>
      <div className="stat-card__trend stat-card__trend--up">↑ +18% this week</div>
    </div>
  ),
};

export const WithTrendDown: Story = {
  name: "With Trend Down",
  render: () => (
    <div className="stat-card stat-card--danger" style={{ width: "200px" }}>
      <div className="stat-card__label">Error Rate</div>
      <div className="stat-card__value">2.4%</div>
      <div className="stat-card__trend stat-card__trend--down">↓ -0.3% vs last week</div>
    </div>
  ),
};

export const AllVariants: Story = {
  name: "All Variants",
  render: () => (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-4)" }}>
      <div className="stat-card" style={{ width: "180px" }}>
        <div className="stat-card__label">Default</div>
        <div className="stat-card__value">42</div>
      </div>
      <div className="stat-card stat-card--accent" style={{ width: "180px" }}>
        <div className="stat-card__label">Accent</div>
        <div className="stat-card__value">128</div>
        <div className="stat-card__trend stat-card__trend--up">+12</div>
      </div>
      <div className="stat-card stat-card--success" style={{ width: "180px" }}>
        <div className="stat-card__label">Success</div>
        <div className="stat-card__value">99.8%</div>
        <div className="stat-card__trend stat-card__trend--up">↑ +0.2%</div>
      </div>
      <div className="stat-card stat-card--danger" style={{ width: "180px" }}>
        <div className="stat-card__label">Danger</div>
        <div className="stat-card__value">4</div>
        <div className="stat-card__trend stat-card__trend--down">↓ -2</div>
      </div>
    </div>
  ),
};
