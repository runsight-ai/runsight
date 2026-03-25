import type { Meta, StoryObj } from "@storybook/react"
import React from "react"

import { ActionCard } from "@/components/ui/action-card"

const meta: Meta<typeof ActionCard> = {
  title: "Data Display/ActionCard",
  component: ActionCard,
  parameters: {
    layout: "padded",
  },
  argTypes: {
    variant: {
      control: "select",
      options: ["default", "accent", "success", "danger", "warning"],
    },
  },
}

export default meta

type Story = StoryObj<typeof ActionCard>

// ---------------------------------------------------------------------------
// Default — basic action card with title and description
// ---------------------------------------------------------------------------

export const Default: Story = {
  args: {
    title: "Connect GitHub",
    description: "Link your GitHub account to enable GitOps workflows and version control.",
    variant: "default",
  },
}

// ---------------------------------------------------------------------------
// WithActionButton — card with title, description, and action button
// ---------------------------------------------------------------------------

export const WithActionButton: Story = {
  name: "With Action Button",
  render: () => (
    <ActionCard
      variant="accent"
      title="Deploy Workflow"
      description="Push the latest version of this workflow to production."
      action={
        <button
          type="button"
          className="rounded-radius-md bg-interactive-default px-3 py-1.5 text-font-size-xs font-medium text-white hover:opacity-90"
        >
          Deploy
        </button>
      }
    />
  ),
}

// ---------------------------------------------------------------------------
// StripeVariants — demonstrates all left stripe color variants
// ---------------------------------------------------------------------------

export const StripeVariants: Story = {
  name: "Stripe Variants",
  render: () => (
    <div className="flex flex-col gap-3 max-w-lg">
      <ActionCard
        variant="default"
        title="Default Stripe"
        description="Uses the default border color for the left stripe."
      />
      <ActionCard
        variant="accent"
        title="Accent Stripe"
        description="Interactive accent color stripe — used for primary actions."
        action={<button type="button" className="text-font-size-xs text-secondary">Configure</button>}
      />
      <ActionCard
        variant="success"
        title="Success Stripe"
        description="Green stripe — used for successful states or recommendations."
      />
      <ActionCard
        variant="danger"
        title="Danger Stripe"
        description="Red stripe — used for warnings, errors, or destructive actions."
        action={<button type="button" className="text-font-size-xs text-danger">Delete</button>}
      />
      <ActionCard
        variant="warning"
        title="Warning Stripe"
        description="Amber stripe — used for cautions or degraded states."
      />
    </div>
  ),
}

// ---------------------------------------------------------------------------
// WithVariantColor — explicit variant and color control
// ---------------------------------------------------------------------------

export const WithVariantColor: Story = {
  name: "Color Variant",
  args: {
    title: "Upgrade Required",
    description: "This feature requires a Pro plan.",
    variant: "warning",
    action: undefined,
  },
}
