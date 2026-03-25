import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

// ActionCard is a card with a left accent stripe, implemented using the
// .card component with inline border-left override per variant.
const meta = {
  title: "Data Display/ActionCard",
  parameters: { layout: "padded" },
};
export default meta;

type Story = StoryObj;

const stripeColors: Record<string, string> = {
  default: "var(--border-default)",
  accent: "var(--interactive-default)",
  success: "var(--success-9)",
  danger: "var(--danger-9)",
  warning: "var(--warning-9)",
};

function ActionCard({ title, description, variant = "default", action }: {
  title: string;
  description?: string;
  variant?: "default" | "accent" | "success" | "danger" | "warning";
  action?: React.ReactNode;
}) {
  return (
    <div className="card" style={{ borderLeft: `3px solid ${stripeColors[variant]}`, maxWidth: "480px" }}>
      <div className="card__body">
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "var(--space-3)" }}>
          <div>
            <div style={{ fontSize: "var(--font-size-md)", fontWeight: "var(--font-weight-medium)", color: "var(--text-heading)", marginBottom: description ? "var(--space-1)" : 0 }}>
              {title}
            </div>
            {description && (
              <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)", margin: 0 }}>{description}</p>
            )}
          </div>
          {action && <div style={{ flexShrink: 0 }}>{action}</div>}
        </div>
      </div>
    </div>
  );
}

export const Default: Story = {
  render: () => (
    <ActionCard
      title="Connect GitHub"
      description="Link your GitHub account to enable GitOps workflows and version control."
      variant="default"
    />
  ),
};

export const WithActionButton: Story = {
  name: "With Action Button",
  render: () => (
    <ActionCard
      variant="accent"
      title="Deploy Workflow"
      description="Push the latest version of this workflow to production."
      action={<button className="btn btn--primary btn--xs">Deploy</button>}
    />
  ),
};

export const StripeVariants: Story = {
  name: "Stripe Variants",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", maxWidth: "480px" }}>
      <ActionCard variant="default" title="Default Stripe" description="Uses the default border color for the left stripe." />
      <ActionCard variant="accent" title="Accent Stripe" description="Interactive accent color stripe — used for primary actions."
        action={<button className="btn btn--ghost btn--xs">Configure</button>}
      />
      <ActionCard variant="success" title="Success Stripe" description="Green stripe — used for successful states or recommendations." />
      <ActionCard variant="danger" title="Danger Stripe" description="Red stripe — used for warnings, errors, or destructive actions."
        action={<button className="btn btn--danger btn--xs">Delete</button>}
      />
      <ActionCard variant="warning" title="Warning Stripe" description="Amber stripe — used for cautions or degraded states." />
    </div>
  ),
};

export const WithVariantColor: Story = {
  name: "Color Variant",
  render: () => (
    <ActionCard
      title="Upgrade Required"
      description="This feature requires a Pro plan."
      variant="warning"
    />
  ),
};
