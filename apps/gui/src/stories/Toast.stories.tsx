import type { Meta, StoryObj } from "@storybook/react"
import React from "react"

import { Toast } from "@/components/ui/toast"

const meta: Meta<typeof Toast> = {
  title: "Primitives/Toast",
  component: Toast,
  parameters: {
    layout: "centered",
  },
  argTypes: {
    variant: {
      control: "select",
      options: ["success", "danger", "warning", "info"],
    },
    title: { control: "text" },
    description: { control: "text" },
  },
}

export default meta

type Story = StoryObj<typeof Toast>

export const Success: Story = {
  name: "Variant: success",
  args: {
    variant: "success",
    title: "Workflow saved",
    description: "Your workflow has been saved successfully.",
  },
}

export const Danger: Story = {
  name: "Variant: danger",
  args: {
    variant: "danger",
    title: "Execution failed",
    description: "Step 3 encountered an unrecoverable error.",
  },
}

export const Warning: Story = {
  name: "Variant: warning",
  args: {
    variant: "warning",
    title: "Token limit approaching",
    description: "This workflow is consuming tokens faster than expected.",
  },
}

export const Info: Story = {
  name: "Variant: info",
  args: {
    variant: "info",
    title: "Workflow queued",
    description: "Your workflow has been added to the execution queue.",
  },
}

export const WithDismiss: Story = {
  name: "With dismiss button",
  render: () => (
    <Toast
      variant="info"
      title="New update available"
      description="Runsight v1.2 is ready to install."
      onDismiss={() => console.log("dismissed")}
    />
  ),
}

export const AllVariants: Story = {
  name: "All Variants",
  render: () => (
    <div className="flex w-80 flex-col gap-3 p-4">
      <Toast
        variant="success"
        title="Workflow saved"
        description="Changes saved successfully."
        onDismiss={() => {}}
      />
      <Toast
        variant="danger"
        title="Execution failed"
        description="An error occurred during execution."
        onDismiss={() => {}}
      />
      <Toast
        variant="warning"
        title="Rate limit warning"
        description="Approaching API rate limit."
        onDismiss={() => {}}
      />
      <Toast
        variant="info"
        title="Workflow queued"
        description="Processing will begin shortly."
        onDismiss={() => {}}
      />
    </div>
  ),
}
