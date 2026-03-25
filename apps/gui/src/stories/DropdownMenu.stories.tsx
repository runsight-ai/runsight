import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Overlays/DropdownMenu",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <div style={{ position: "relative", display: "inline-block" }}>
      <div className="dropdown-menu" style={{ position: "static" }}>
        <div className="dropdown-menu__item">New Workflow</div>
        <div className="dropdown-menu__item">Duplicate</div>
        <div className="dropdown-menu__item">Rename</div>
        <div className="dropdown-menu__separator" />
        <div className="dropdown-menu__item dropdown-menu__item--danger">Delete</div>
      </div>
    </div>
  ),
};

export const WithSeparatorAndGroups: Story = {
  name: "With Separator and Groups",
  render: () => (
    <div className="dropdown-menu" style={{ position: "static", minWidth: "200px" }}>
      <div className="dropdown-menu__section-label">Workflow</div>
      <div className="dropdown-menu__item">
        <span className="dropdown-menu__item-label">Run Now</span>
        <span className="dropdown-menu__item-shortcut">⌘R</span>
      </div>
      <div className="dropdown-menu__item">
        <span className="dropdown-menu__item-label">Schedule</span>
        <span className="dropdown-menu__item-shortcut">⌘S</span>
      </div>
      <div className="dropdown-menu__separator" />
      <div className="dropdown-menu__section-label">Edit</div>
      <div className="dropdown-menu__item">
        <span className="dropdown-menu__item-label">Duplicate</span>
        <span className="dropdown-menu__item-shortcut">⌘D</span>
      </div>
      <div className="dropdown-menu__item">Rename</div>
      <div className="dropdown-menu__separator" />
      <div className="dropdown-menu__item dropdown-menu__item--danger">Delete Workflow</div>
    </div>
  ),
};

export const WithIcons: Story = {
  name: "With Icons and Sections",
  render: () => (
    <div className="dropdown-menu" style={{ position: "static", minWidth: "200px" }}>
      <div className="dropdown-menu__section-label">Account</div>
      <div className="dropdown-menu__item">
        <svg className="dropdown-menu__item-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
          <path d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
        </svg>
        <span className="dropdown-menu__item-label">Profile</span>
      </div>
      <div className="dropdown-menu__item">
        <svg className="dropdown-menu__item-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
          <path d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z" />
        </svg>
        <span className="dropdown-menu__item-label">API Keys</span>
      </div>
      <div className="dropdown-menu__separator" />
      <div className="dropdown-menu__item dropdown-menu__item--danger">Sign Out</div>
    </div>
  ),
};
