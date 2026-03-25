import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { ActionCard } from "@/components/ui/action-card";
import { Button } from "@/components/ui/button";

const meta: Meta<typeof ActionCard> = {
  title: "Data Display/ActionCard",
  component: ActionCard,
  parameters: { layout: "padded" },
  argTypes: {
    title: {
      control: { type: "text" },
      description: "Card title — displayed with text-heading",
    },
    description: {
      control: { type: "text" },
      description: "Card description — displayed with text-secondary and font-size-sm",
    },
    variant: {
      control: { type: "select" },
      options: ["default", "accent", "success", "danger", "warning"],
      description: "Variant controls the left 3px accent stripe color",
    },
    action: {
      control: false,
      description: "Action area — typically a Button or link (ReactNode)",
    },
  },
};
export default meta;

type Story = StoryObj<typeof ActionCard>;

export const Default: Story = {
  name: "Default (controls)",
  args: {
    title: "Connect GitHub",
    description: "Link your GitHub account to enable GitOps workflows and version control.",
    variant: "default",
  },
  render: (args) => (
    <div style={{ maxWidth: "480px" }}>
      <ActionCard {...args} />
    </div>
  ),
};

export const WithAction: Story = {
  name: "With Action",
  render: () => (
    <div style={{ maxWidth: "480px" }}>
      <ActionCard
        title="Deploy Workflow"
        description="Push the latest version of this workflow to production."
        variant="accent"
        action={<Button variant="primary" size="xs">Deploy</Button>}
      />
    </div>
  ),
};

export const AllVariants: Story = {
  name: "All Variants",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", maxWidth: "480px" }}>
      <ActionCard
        title="Default Stripe"
        description="Uses the default border color for the left stripe."
        variant="default"
      />
      <ActionCard
        title="Accent Stripe"
        description="Interactive accent color stripe — used for primary actions."
        variant="accent"
        action={<Button variant="ghost" size="xs">Configure</Button>}
      />
      <ActionCard
        title="Success Stripe"
        description="Green stripe — used for successful states or recommendations."
        variant="success"
      />
      <ActionCard
        title="Danger Stripe"
        description="Red stripe — used for warnings, errors, or destructive actions."
        variant="danger"
        action={<Button variant="danger" size="xs">Delete</Button>}
      />
      <ActionCard
        title="Warning Stripe"
        description="Amber stripe — used for cautions or degraded states."
        variant="warning"
      />
    </div>
  ),
};
