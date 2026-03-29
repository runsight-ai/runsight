import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { Toast } from "../components/ui/toast";

const meta: Meta<typeof Toast> = {
  title: "Primitives/Toast",
  component: Toast,
  parameters: { layout: "centered" },
  argTypes: {
    variant: {
      control: { type: "select" },
      options: ["success", "danger", "warning", "info"],
      description: "Semantic variant of the toast",
    },
    title: {
      control: { type: "text" },
      description: "Toast title text",
    },
    description: {
      control: { type: "text" },
      description: "Toast description text",
    },
    onDismiss: {
      action: "dismissed",
      description: "Callback when dismiss button is clicked. If provided, dismiss button is rendered.",
    },
  },
};
export default meta;

type Story = StoryObj<typeof Toast>;

export const Default: Story = {
  name: "Default (controls)",
  args: {
    variant: "info",
    title: "Workflow queued",
    description: "Your workflow has been added to the execution queue.",
  },
  decorators: [
    (Story) => (
      <div style={{ minWidth: "320px" }}>
        <Story />
      </div>
    ),
  ],
};

export const AllVariants: Story = {
  name: "All Variants",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", width: "360px" }}>
      <Toast
        variant="success"
        title="Workflow saved"
        description="Changes saved successfully."
      />
      <Toast
        variant="danger"
        title="Execution failed"
        description="An error occurred during execution."
      />
      <Toast
        variant="warning"
        title="Rate limit warning"
        description="Approaching API rate limit."
      />
      <Toast
        variant="info"
        title="Workflow queued"
        description="Processing will begin shortly."
      />
    </div>
  ),
};

export const WithDismiss: Story = {
  name: "With Dismiss",
  render: () => (
    <div style={{ minWidth: "320px" }}>
      <Toast
        variant="info"
        title="New update available"
        description="Runsight v1.2 is ready to install."
        onDismiss={() => alert("dismissed")}
      />
    </div>
  ),
};
