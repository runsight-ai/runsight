import type { Meta, StoryObj } from "@storybook/react"
import React from "react"

import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"

const meta: Meta<typeof Tabs> = {
  title: "Navigation/Tabs",
  component: Tabs,
  parameters: {
    layout: "centered",
  },
}

export default meta

type Story = StoryObj<typeof Tabs>

export const Default: Story = {
  render: () => (
    <Tabs defaultValue="overview">
      <TabsList>
        <TabsTrigger value="overview">Overview</TabsTrigger>
        <TabsTrigger value="runs">Runs</TabsTrigger>
        <TabsTrigger value="settings">Settings</TabsTrigger>
      </TabsList>
      <TabsContent value="overview">
        <p className="text-sm text-text-secondary pt-4">Overview content</p>
      </TabsContent>
      <TabsContent value="runs">
        <p className="text-sm text-text-secondary pt-4">Runs content</p>
      </TabsContent>
      <TabsContent value="settings">
        <p className="text-sm text-text-secondary pt-4">Settings content</p>
      </TabsContent>
    </Tabs>
  ),
}

export const LineUnderline: Story = {
  name: "Line (Underline Indicator)",
  render: () => (
    <Tabs defaultValue="workflows">
      <TabsList variant="line">
        <TabsTrigger value="workflows">Workflows</TabsTrigger>
        <TabsTrigger value="souls">Souls</TabsTrigger>
        <TabsTrigger value="steps">Steps</TabsTrigger>
        <TabsTrigger value="runs">Runs</TabsTrigger>
      </TabsList>
      <TabsContent value="workflows">
        <p className="text-sm text-text-secondary pt-4">Workflows list</p>
      </TabsContent>
      <TabsContent value="souls">
        <p className="text-sm text-text-secondary pt-4">Souls list</p>
      </TabsContent>
      <TabsContent value="steps">
        <p className="text-sm text-text-secondary pt-4">Steps list</p>
      </TabsContent>
      <TabsContent value="runs">
        <p className="text-sm text-text-secondary pt-4">Runs list</p>
      </TabsContent>
    </Tabs>
  ),
}

export const Overflow: Story = {
  name: "Overflow (Many Tabs)",
  render: () => (
    <div style={{ width: 320, overflow: "hidden" }}>
      <Tabs defaultValue="tab1">
        <TabsList variant="line">
          {Array.from({ length: 10 }, (_, i) => (
            <TabsTrigger key={i} value={`tab${i + 1}`}>
              Tab {i + 1}
            </TabsTrigger>
          ))}
        </TabsList>
        {Array.from({ length: 10 }, (_, i) => (
          <TabsContent key={i} value={`tab${i + 1}`}>
            <p className="text-sm text-text-secondary pt-4">Tab {i + 1} content</p>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  ),
}

export const Disabled: Story = {
  render: () => (
    <Tabs defaultValue="active">
      <TabsList>
        <TabsTrigger value="active">Active</TabsTrigger>
        <TabsTrigger value="disabled" disabled>
          Disabled
        </TabsTrigger>
        <TabsTrigger value="another">Another</TabsTrigger>
      </TabsList>
      <TabsContent value="active">
        <p className="text-sm text-text-secondary pt-4">Active tab content</p>
      </TabsContent>
    </Tabs>
  ),
}
