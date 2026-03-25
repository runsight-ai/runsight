import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { Tabs, TabsList, TabsTrigger, TabsContent, TabBadge } from "@/components/ui/tabs";

// Tabs uses @base-ui/react/tabs under the hood.
// TabsList `variant` prop maps to: "default" → .tabs, "contained" → .tabs--contained, "vertical" → .tabs--vertical
const meta: Meta<typeof TabsList> = {
  title: "Navigation/Tabs",
  component: TabsList,
  parameters: { layout: "padded" },
  argTypes: {
    variant: {
      control: { type: "select" },
      options: ["default", "contained", "vertical"],
      description: "TabsList layout/style variant",
    },
  },
};
export default meta;

type Story = StoryObj<typeof TabsList>;

export const Default: Story = {
  name: "Default (controls)",
  args: {
    variant: "default",
  },
  render: (args) => (
    <div style={{ width: "400px" }}>
      <Tabs defaultValue="overview">
        <TabsList variant={args.variant}>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="runs">Runs</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
        </TabsList>
        <TabsContent value="overview">
          <p style={{ paddingTop: "var(--space-4)", fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>
            Overview content
          </p>
        </TabsContent>
        <TabsContent value="runs">
          <p style={{ paddingTop: "var(--space-4)", fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>
            Runs content
          </p>
        </TabsContent>
        <TabsContent value="settings">
          <p style={{ paddingTop: "var(--space-4)", fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>
            Settings content
          </p>
        </TabsContent>
      </Tabs>
    </div>
  ),
};

export const Contained: Story = {
  name: "Contained",
  render: () => (
    <div style={{ width: "400px" }}>
      <Tabs defaultValue="overview">
        <TabsList variant="contained">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="runs">Runs</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
        </TabsList>
        <TabsContent value="overview">
          <p style={{ paddingTop: "var(--space-4)", fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>
            Overview content
          </p>
        </TabsContent>
        <TabsContent value="runs">
          <p style={{ paddingTop: "var(--space-4)", fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>
            Runs content
          </p>
        </TabsContent>
        <TabsContent value="settings">
          <p style={{ paddingTop: "var(--space-4)", fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>
            Settings content
          </p>
        </TabsContent>
      </Tabs>
    </div>
  ),
};

export const Vertical: Story = {
  name: "Vertical",
  render: () => (
    <div style={{ width: "400px" }}>
      <Tabs defaultValue="overview" orientation="vertical" style={{ display: "flex", gap: "var(--space-4)" }}>
        <TabsList variant="vertical">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="runs">Runs</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
        </TabsList>
        <div style={{ flex: 1 }}>
          <TabsContent value="overview">
            <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>Overview content</p>
          </TabsContent>
          <TabsContent value="runs">
            <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>Runs content</p>
          </TabsContent>
          <TabsContent value="settings">
            <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>Settings content</p>
          </TabsContent>
        </div>
      </Tabs>
    </div>
  ),
};

export const WithBadge: Story = {
  name: "With Badge (.tab__badge)",
  render: () => (
    <div style={{ width: "480px" }}>
      <Tabs defaultValue="runs">
        <TabsList variant="default">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="runs">
            Runs <TabBadge>48</TabBadge>
          </TabsTrigger>
          <TabsTrigger value="failed">
            Failed <TabBadge>6</TabBadge>
          </TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
        </TabsList>
        <TabsContent value="overview">
          <p style={{ paddingTop: "var(--space-4)", fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>
            Overview content
          </p>
        </TabsContent>
        <TabsContent value="runs">
          <p style={{ paddingTop: "var(--space-4)", fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>
            48 total runs
          </p>
        </TabsContent>
        <TabsContent value="failed">
          <p style={{ paddingTop: "var(--space-4)", fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>
            6 failed runs
          </p>
        </TabsContent>
        <TabsContent value="settings">
          <p style={{ paddingTop: "var(--space-4)", fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>
            Settings content
          </p>
        </TabsContent>
      </Tabs>
    </div>
  ),
};

export const WithContent: Story = {
  name: "With Content",
  render: () => (
    <div style={{ width: "480px" }}>
      <Tabs defaultValue="workflows">
        <TabsList variant="default">
          <TabsTrigger value="workflows">Workflows</TabsTrigger>
          <TabsTrigger value="souls">Souls</TabsTrigger>
          <TabsTrigger value="steps">Steps</TabsTrigger>
          <TabsTrigger value="runs">Runs</TabsTrigger>
        </TabsList>
        <TabsContent value="workflows">
          <div style={{ paddingTop: "var(--space-4)", fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>
            <p>6 workflows — 3 active, 2 draft, 1 archived.</p>
          </div>
        </TabsContent>
        <TabsContent value="souls">
          <div style={{ paddingTop: "var(--space-4)", fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>
            <p>4 souls configured across all workflows.</p>
          </div>
        </TabsContent>
        <TabsContent value="steps">
          <div style={{ paddingTop: "var(--space-4)", fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>
            <p>12 steps defined in the current workspace.</p>
          </div>
        </TabsContent>
        <TabsContent value="runs">
          <div style={{ paddingTop: "var(--space-4)", fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>
            <p>48 total runs — 42 succeeded, 6 failed.</p>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  ),
};
