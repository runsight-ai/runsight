import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Overlays/Command",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <div className="command-palette" style={{ position: "static", transform: "none", width: "480px" }}>
      <div className="command-palette__input-wrapper">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" style={{ color: "var(--text-muted)", flexShrink: 0 }}>
          <path d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 15.803a7.5 7.5 0 0010.607 0z" />
        </svg>
        <input className="command-palette__input" type="text" placeholder="Search commands..." />
      </div>
      <div className="command-palette__results">
        <div className="command-palette__group-label">Workflows</div>
        <div className="command-palette__item">New Workflow</div>
        <div className="command-palette__item">Open Workflow</div>
        <div className="command-palette__item">Clone Workflow</div>
        <div className="command-palette__group-label" style={{ marginTop: "var(--space-2)" }}>Souls</div>
        <div className="command-palette__item">New Soul</div>
        <div className="command-palette__item">Edit Soul</div>
      </div>
      <div className="command-palette__footer">
        <span><kbd>↑↓</kbd> navigate</span>
        <span><kbd>↵</kbd> select</span>
        <span><kbd>esc</kbd> close</span>
      </div>
    </div>
  ),
};

export const WithShortcuts: Story = {
  name: "With Keyboard Shortcuts",
  render: () => (
    <div className="command-palette" style={{ position: "static", transform: "none", width: "480px" }}>
      <div className="command-palette__input-wrapper">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" style={{ color: "var(--text-muted)", flexShrink: 0 }}>
          <path d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 15.803a7.5 7.5 0 0010.607 0z" />
        </svg>
        <input className="command-palette__input" type="text" placeholder="Type a command or search..." />
      </div>
      <div className="command-palette__results">
        <div className="command-palette__group-label">Actions</div>
        <div className="command-palette__item">
          <span className="command-palette__item-label">Run Workflow</span>
          <span className="command-palette__item-shortcut">⌘R</span>
        </div>
        <div className="command-palette__item" aria-selected="true">
          <span className="command-palette__item-label">Open Canvas</span>
          <span className="command-palette__item-shortcut">⌘K</span>
        </div>
        <div className="command-palette__item">
          <span className="command-palette__item-label">Commit Changes</span>
          <span className="command-palette__item-shortcut">⌘G</span>
        </div>
        <div className="command-palette__item">
          <span className="command-palette__item-label">Deploy</span>
          <span className="command-palette__item-shortcut">⌘⇧D</span>
        </div>
        <div className="command-palette__group-label" style={{ marginTop: "var(--space-2)" }}>Navigation</div>
        <div className="command-palette__item">
          <span className="command-palette__item-label">Go to Runs</span>
          <span className="command-palette__item-shortcut">⌘1</span>
        </div>
        <div className="command-palette__item">
          <span className="command-palette__item-label">Go to Workflows</span>
          <span className="command-palette__item-shortcut">⌘2</span>
        </div>
        <div className="command-palette__item">
          <span className="command-palette__item-label">Go to Settings</span>
          <span className="command-palette__item-shortcut">⌘,</span>
        </div>
      </div>
      <div className="command-palette__footer">
        <span><kbd>↑↓</kbd> navigate</span>
        <span><kbd>↵</kbd> select</span>
        <span><kbd>esc</kbd> close</span>
      </div>
    </div>
  ),
};

export const Basic: Story = {
  render: () => (
    <div className="command-palette" style={{ position: "static", transform: "none", width: "400px" }}>
      <div className="command-palette__input-wrapper">
        <input className="command-palette__input" type="text" placeholder="Search..." />
      </div>
      <div className="command-palette__results">
        <div className="command-palette__group-label">Recent</div>
        <div className="command-palette__item">agent-pipeline-v2</div>
        <div className="command-palette__item">data-enrichment-flow</div>
        <div className="command-palette__item">customer-onboarding</div>
      </div>
    </div>
  ),
};
