import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetBody,
  SheetTrigger,
} from "../components/ui/sheet";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";

const meta: Meta<typeof SheetContent> = {
  title: "Overlays/Sheet",
  component: SheetContent,
  parameters: { layout: "centered" },
  argTypes: {
    side: {
      control: { type: "select" },
      options: ["right", "bottom"],
      description: "Which edge the sheet slides in from",
    },
  },
};
export default meta;

type Story = StoryObj<typeof SheetContent>;

export const Default: Story = {
  name: "Default (controls)",
  args: {
    side: "right",
  },
  render: (args) => (
    <Sheet>
      <SheetTrigger render={<Button variant="secondary">Open Sheet</Button>} />
      <SheetContent {...args}>
        <SheetHeader>
          <SheetTitle>Workflow Details</SheetTitle>
        </SheetHeader>
        <SheetBody>
          <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>
            View and edit the details for this workflow.
          </p>
        </SheetBody>
      </SheetContent>
    </Sheet>
  ),
};

export const Right: Story = {
  name: "Side — Right",
  render: () => (
    <Sheet>
      <SheetTrigger render={<Button variant="secondary">Open Right Panel</Button>} />
      <SheetContent side="right">
        <SheetHeader>
          <SheetTitle>Workflow Details</SheetTitle>
        </SheetHeader>
        <SheetBody>
          <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)", marginBottom: "var(--space-4)" }}>
            View and edit the details for this workflow.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
              <Label htmlFor="sheet-name">Workflow Name</Label>
              <Input id="sheet-name" defaultValue="customer-support-triage" />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
              <Label htmlFor="sheet-desc">Description</Label>
              <Input id="sheet-desc" defaultValue="Classifies and routes incoming support tickets." />
            </div>
          </div>
        </SheetBody>
      </SheetContent>
    </Sheet>
  ),
};

export const Bottom: Story = {
  name: "Side — Bottom",
  render: () => (
    <Sheet>
      <SheetTrigger render={<Button variant="secondary">Open Bottom Panel</Button>} />
      <SheetContent side="bottom">
        <SheetHeader>
          <SheetTitle>Bottom Panel</SheetTitle>
        </SheetHeader>
        <SheetBody>
          <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-muted)" }}>
            Slides up from the bottom of the screen.
          </p>
        </SheetBody>
      </SheetContent>
    </Sheet>
  ),
};
