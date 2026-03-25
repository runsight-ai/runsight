import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";

const meta: Meta = {
  title: "Overlays/Sheet",
  parameters: {
    layout: "centered",
  },
};

export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <Sheet>
      <SheetTrigger render={<Button variant="secondary">Open Sheet</Button>} />
      <SheetContent side="right">
        <SheetHeader>
          <SheetTitle>Workflow Details</SheetTitle>
          <SheetDescription>
            View and edit the details for this workflow.
          </SheetDescription>
        </SheetHeader>
        <div className="px-4 flex flex-col gap-3 text-sm">
          <p>This is the sheet body. Add form fields or content here.</p>
        </div>
        <SheetFooter>
          <Button variant="primary" size="sm">Save</Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  ),
};

export const RightSide: Story = {
  name: "Side — Right",
  render: () => (
    <Sheet>
      <SheetTrigger render={<Button variant="secondary">Right Side</Button>} />
      <SheetContent side="right">
        <SheetHeader>
          <SheetTitle>Right Panel</SheetTitle>
          <SheetDescription>Slides in from the right side.</SheetDescription>
        </SheetHeader>
        <div className="px-4 text-sm text-muted">Right-side sheet content.</div>
      </SheetContent>
    </Sheet>
  ),
};

export const LeftSide: Story = {
  name: "Side — Left",
  render: () => (
    <Sheet>
      <SheetTrigger render={<Button variant="secondary">Left Side</Button>} />
      <SheetContent side="left">
        <SheetHeader>
          <SheetTitle>Left Panel</SheetTitle>
          <SheetDescription>Slides in from the left side.</SheetDescription>
        </SheetHeader>
        <div className="px-4 text-sm text-muted">Left-side sheet content.</div>
      </SheetContent>
    </Sheet>
  ),
};

export const BottomSide: Story = {
  name: "Side — Bottom",
  render: () => (
    <Sheet>
      <SheetTrigger render={<Button variant="secondary">Bottom Side</Button>} />
      <SheetContent side="bottom">
        <SheetHeader>
          <SheetTitle>Bottom Panel</SheetTitle>
          <SheetDescription>Slides up from the bottom.</SheetDescription>
        </SheetHeader>
        <div className="px-4 text-sm text-muted">Bottom-side sheet content.</div>
      </SheetContent>
    </Sheet>
  ),
};

export const TopSide: Story = {
  name: "Side — Top",
  render: () => (
    <Sheet>
      <SheetTrigger render={<Button variant="secondary">Top Side</Button>} />
      <SheetContent side="top">
        <SheetHeader>
          <SheetTitle>Top Panel</SheetTitle>
          <SheetDescription>Slides down from the top.</SheetDescription>
        </SheetHeader>
        <div className="px-4 text-sm text-muted">Top-side sheet content.</div>
      </SheetContent>
    </Sheet>
  ),
};
