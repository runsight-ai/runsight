import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogBody,
  DialogFooter,
  DialogTrigger,
  DialogClose,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const meta: Meta<typeof DialogContent> = {
  title: "Overlays/Dialog",
  component: DialogContent,
  parameters: { layout: "centered" },
  argTypes: {
    size: {
      control: { type: "select" },
      options: ["sm", "md", "lg"],
      description: "Width size of the dialog",
    },
  },
};
export default meta;

type Story = StoryObj<typeof DialogContent>;

export const Default: Story = {
  name: "Default (controls)",
  args: {
    size: "md",
  },
  render: (args) => (
    <Dialog>
      <DialogTrigger render={<Button variant="secondary">Open Dialog</Button>} />
      <DialogContent {...args}>
        <DialogHeader>
          <DialogTitle>Workflow Settings</DialogTitle>
        </DialogHeader>
        <DialogBody>
          <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>
            Configure settings for this workflow. Changes are saved automatically.
          </p>
        </DialogBody>
        <DialogFooter showCloseButton>
          <Button variant="primary" size="sm">Save Changes</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  ),
};

export const Confirmation: Story = {
  render: () => (
    <Dialog>
      <DialogTrigger render={<Button variant="danger">Delete Workflow</Button>} />
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle>Delete Workflow</DialogTitle>
        </DialogHeader>
        <DialogBody>
          <p style={{ fontSize: "var(--font-size-md)", color: "var(--text-secondary)" }}>
            This action cannot be undone. The workflow and all its run history will be permanently removed.
          </p>
        </DialogBody>
        <DialogFooter>
          <DialogClose render={<Button variant="outline" size="sm">Cancel</Button>} />
          <Button variant="danger" size="sm">Delete</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  ),
};

export const WithForm: Story = {
  name: "With Form",
  render: () => (
    <Dialog>
      <DialogTrigger render={<Button variant="secondary">Edit Soul</Button>} />
      <DialogContent size="md">
        <DialogHeader>
          <DialogTitle>Edit Soul</DialogTitle>
        </DialogHeader>
        <DialogBody>
          <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)", marginBottom: "var(--space-4)" }}>
            Update the identity and prompt for this agent soul.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
              <Label htmlFor="soul-name">Name</Label>
              <Input id="soul-name" defaultValue="Planner Soul" />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
              <Label htmlFor="soul-model">Model</Label>
              <Input id="soul-model" defaultValue="claude-3-5-sonnet" />
            </div>
          </div>
        </DialogBody>
        <DialogFooter>
          <DialogClose render={<Button variant="outline" size="sm">Cancel</Button>} />
          <Button variant="primary" size="sm">Save Changes</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  ),
};
