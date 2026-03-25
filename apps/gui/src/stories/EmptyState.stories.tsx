import type { Meta, StoryObj } from "@storybook/react";
import React from "react";
import { Inbox, Search, FolderOpen, Zap, AlertCircle } from "lucide-react";

import { EmptyState } from "@/components/shared/EmptyState";

const meta: Meta<typeof EmptyState> = {
  title: "Composites/EmptyState",
  component: EmptyState,
  parameters: {
    layout: "centered",
  },
};

export default meta;

type Story = StoryObj<typeof EmptyState>;

// ---------------------------------------------------------------------------
// Default — title + description + no action
// ---------------------------------------------------------------------------

export const Default: Story = {
  args: {
    icon: Inbox,
    title: "No workflows yet",
    description: "Create your first workflow to get started with agent orchestration.",
  },
};

// ---------------------------------------------------------------------------
// With action button
// ---------------------------------------------------------------------------

export const WithAction: Story = {
  name: "With action button",
  args: {
    icon: Zap,
    title: "No runs yet",
    description: "Trigger your first workflow run to see execution details here.",
    action: {
      label: "Run workflow",
      onClick: () => undefined,
    },
  },
};

// ---------------------------------------------------------------------------
// Without description (title-only)
// ---------------------------------------------------------------------------

export const WithoutDescription: Story = {
  name: "WithoutDescription (title only)",
  args: {
    icon: FolderOpen,
    title: "Nothing here yet",
  },
};

// ---------------------------------------------------------------------------
// No description + action
// ---------------------------------------------------------------------------

export const TitleWithAction: Story = {
  name: "Title + action (no description)",
  args: {
    icon: Search,
    title: "No results found",
    action: {
      label: "Clear filters",
      onClick: () => undefined,
    },
  },
};

// ---------------------------------------------------------------------------
// Error / warning variant
// ---------------------------------------------------------------------------

export const ErrorState: Story = {
  name: "Error / warning state",
  args: {
    icon: AlertCircle,
    title: "Failed to load workflows",
    description: "Check your connection or try refreshing the page.",
    action: {
      label: "Retry",
      onClick: () => undefined,
    },
  },
};
