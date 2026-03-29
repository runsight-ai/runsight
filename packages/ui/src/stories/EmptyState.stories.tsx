import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { EmptyState } from "../components/shared/EmptyState";
import { InboxIcon, ZapIcon, SearchIcon, AlertCircleIcon, WorkflowIcon } from "lucide-react";

const meta: Meta<typeof EmptyState> = {
  title: "Composites/EmptyState",
  component: EmptyState,
  parameters: { layout: "centered" },
  argTypes: {
    title: { control: "text" },
    description: { control: "text" },
    icon: { control: false },
  },
};
export default meta;

type Story = StoryObj<typeof EmptyState>;

export const Default: Story = {
  name: "Default (controls)",
  args: {
    icon: InboxIcon,
    title: "No workflows yet",
    description: "Create your first workflow to get started with agent orchestration.",
  },
};

export const WithAction: Story = {
  name: "With Action",
  render: () => (
    <EmptyState
      icon={ZapIcon}
      title="No runs yet"
      description="Trigger your first workflow run to see execution details here."
      action={{ label: "Run workflow", onClick: () => alert("Run workflow clicked") }}
    />
  ),
};

export const NoDescription: Story = {
  name: "No Description",
  render: () => (
    <EmptyState
      icon={WorkflowIcon}
      title="Nothing here yet"
    />
  ),
};

export const WithActionNoDescription: Story = {
  name: "Title + Action (no description)",
  render: () => (
    <EmptyState
      icon={SearchIcon}
      title="No results found"
      action={{ label: "Clear filters", onClick: () => alert("Clear filters clicked") }}
    />
  ),
};

export const ErrorState: Story = {
  name: "Error / Warning state",
  render: () => (
    <EmptyState
      icon={AlertCircleIcon}
      title="Failed to load workflows"
      description="Check your connection or try refreshing the page."
      action={{ label: "Retry", onClick: () => alert("Retry clicked") }}
    />
  ),
};
