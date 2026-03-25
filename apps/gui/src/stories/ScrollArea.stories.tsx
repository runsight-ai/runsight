import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const meta = {
  title: "Overlays/ScrollArea",
  parameters: { layout: "centered" },
};
export default meta;

type Story = StoryObj;

const longContent = Array.from({ length: 40 }, (_, i) => `Item ${i + 1} — workflow step or log entry`);

export const Default: Story = {
  render: () => (
    <div style={{
      height: "288px", width: "256px", overflowY: "auto",
      borderRadius: "var(--radius-lg)", border: "1px solid var(--border-default)",
      background: "var(--surface-primary)", padding: "var(--space-2)"
    }}>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
        {longContent.map((item, i) => (
          <div key={i} style={{
            padding: "var(--space-1) var(--space-2)",
            fontSize: "var(--font-size-sm)", color: "var(--text-primary)",
            borderRadius: "var(--radius-sm)", cursor: "default"
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-hover)")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "")}
          >
            {item}
          </div>
        ))}
      </div>
    </div>
  ),
};

export const Basic: Story = {
  render: () => (
    <div style={{
      height: "192px", width: "224px", overflowY: "auto",
      borderRadius: "var(--radius-lg)", border: "1px solid var(--border-default)"
    }}>
      <div style={{ padding: "var(--space-3)", display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
        {Array.from({ length: 20 }, (_, i) => (
          <p key={i} style={{ fontSize: "var(--font-size-sm)", color: "var(--text-muted)", margin: 0 }}>
            Log line {i + 1}: execution output here
          </p>
        ))}
      </div>
    </div>
  ),
};

export const HorizontalScroll: Story = {
  name: "Horizontal Overflow",
  render: () => (
    <div style={{
      width: "256px", overflowX: "auto",
      borderRadius: "var(--radius-lg)", border: "1px solid var(--border-default)"
    }}>
      <div style={{ display: "flex", gap: "var(--space-3)", padding: "var(--space-3)", width: "max-content" }}>
        {Array.from({ length: 8 }, (_, i) => (
          <div key={i} style={{
            width: "128px", flexShrink: 0, borderRadius: "var(--radius-md)",
            border: "1px solid var(--border-default)", background: "var(--surface-secondary)",
            padding: "var(--space-3)"
          }}>
            <p style={{ fontWeight: "var(--font-weight-medium)", fontSize: "var(--font-size-sm)", color: "var(--text-primary)", margin: 0 }}>
              Step {i + 1}
            </p>
            <p style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", marginTop: "var(--space-1)", marginBottom: 0 }}>
              agent-soul-{i + 1}
            </p>
          </div>
        ))}
      </div>
    </div>
  ),
};
