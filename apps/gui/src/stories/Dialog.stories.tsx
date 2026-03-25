import type { Meta, StoryObj } from "@storybook/react";
import React, { useState } from "react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const meta: Meta = {
  title: "Overlays/Dialog",
  parameters: {
    layout: "centered",
  },
};

export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <Dialog>
      <DialogTrigger render={<Button variant="secondary">Open Dialog</Button>} />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Workflow Settings</DialogTitle>
          <DialogDescription>
            Configure settings for this workflow. Changes are saved automatically.
          </DialogDescription>
        </DialogHeader>
        <p className="text-sm text-muted">
          This is the dialog body. Add any content here.
        </p>
      </DialogContent>
    </Dialog>
  ),
};

export const WithFormAndFooter: Story = {
  name: "With Form and Footer (Actions)",
  render: () => (
    <Dialog>
      <DialogTrigger render={<Button variant="secondary">Edit Soul</Button>} />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Soul</DialogTitle>
          <DialogDescription>
            Update the identity and prompt for this agent soul.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="soul-name">Name</Label>
            <Input id="soul-name" defaultValue="Planner Soul" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="soul-model">Model</Label>
            <Input id="soul-model" defaultValue="claude-3-5-sonnet" />
          </div>
        </div>
        <DialogFooter showCloseButton>
          <Button variant="primary" size="sm">Save Changes</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  ),
};

export const Destructive: Story = {
  render: () => (
    <Dialog>
      <DialogTrigger render={<Button variant="danger">Delete Workflow</Button>} />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete Workflow</DialogTitle>
          <DialogDescription>
            This action cannot be undone. The workflow and all its run history
            will be permanently removed.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter showCloseButton>
          <Button variant="danger" size="sm">Delete</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  ),
};
