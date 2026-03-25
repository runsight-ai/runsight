import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Composites/EmptyState",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

const InboxIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" style={{ width: "100%", height: "100%" }}>
    <path d="M2.25 13.5h3.86a2.25 2.25 0 012.012 1.244l.256.512a2.25 2.25 0 002.013 1.244h3.218a2.25 2.25 0 002.013-1.244l.256-.512a2.25 2.25 0 012.013-1.244h3.859m-19.5.338V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18v-4.162c0-.224-.034-.447-.1-.661L19.24 5.338a2.25 2.25 0 00-2.15-1.588H6.911a2.25 2.25 0 00-2.15 1.588L2.35 13.177a2.25 2.25 0 00-.1.661z" />
  </svg>
);

const ZapIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" style={{ width: "100%", height: "100%" }}>
    <path d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
  </svg>
);

const SearchIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" style={{ width: "100%", height: "100%" }}>
    <path d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 15.803a7.5 7.5 0 0010.607 0z" />
  </svg>
);

const AlertIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" style={{ width: "100%", height: "100%" }}>
    <path d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
  </svg>
);

export const Default: Story = {
  render: () => (
    <div className="empty-state">
      <div className="empty-state__icon"><InboxIcon /></div>
      <div className="empty-state__title">No workflows yet</div>
      <p className="empty-state__description">Create your first workflow to get started with agent orchestration.</p>
    </div>
  ),
};

export const WithAction: Story = {
  name: "With action button",
  render: () => (
    <div className="empty-state">
      <div className="empty-state__icon"><ZapIcon /></div>
      <div className="empty-state__title">No runs yet</div>
      <p className="empty-state__description">Trigger your first workflow run to see execution details here.</p>
      <button className="btn btn--primary btn--sm">Run workflow</button>
    </div>
  ),
};

export const WithoutDescription: Story = {
  name: "Title only",
  render: () => (
    <div className="empty-state">
      <div className="empty-state__icon"><InboxIcon /></div>
      <div className="empty-state__title">Nothing here yet</div>
    </div>
  ),
};

export const TitleWithAction: Story = {
  name: "Title + action (no description)",
  render: () => (
    <div className="empty-state">
      <div className="empty-state__icon"><SearchIcon /></div>
      <div className="empty-state__title">No results found</div>
      <button className="btn btn--secondary btn--sm">Clear filters</button>
    </div>
  ),
};

export const ErrorState: Story = {
  name: "Error / warning state",
  render: () => (
    <div className="empty-state">
      <div className="empty-state__icon" style={{ color: "var(--danger-9)" }}><AlertIcon /></div>
      <div className="empty-state__title">Failed to load workflows</div>
      <p className="empty-state__description">Check your connection or try refreshing the page.</p>
      <button className="btn btn--secondary btn--sm">Retry</button>
    </div>
  ),
};
