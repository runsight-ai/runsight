import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuLabel,
  DropdownMenuGroup,
  DropdownMenuShortcut,
} from "../components/ui/dropdown-menu";
import { Button } from "../components/ui/button";
import { ChevronDownIcon, PlayIcon, CopyIcon, PencilIcon, TrashIcon } from "lucide-react";

const meta: Meta<{ triggerLabel: string }> = {
  title: "Overlays/DropdownMenu",
  parameters: { layout: "centered" },
  argTypes: {
    triggerLabel: {
      control: { type: "text" },
      description: "Label shown on the trigger button",
    },
  },
};
export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  name: "Default (with trigger)",
  args: {
    triggerLabel: "Actions",
  },
  render: (args) => (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button variant="secondary" size="sm">
            {args.triggerLabel} <ChevronDownIcon size={14} />
          </Button>
        }
      />
      <DropdownMenuContent>
        <DropdownMenuItem>New Workflow</DropdownMenuItem>
        <DropdownMenuItem>Duplicate</DropdownMenuItem>
        <DropdownMenuItem>Rename</DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive">Delete</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  ),
};

export const WithSeparators: Story = {
  name: "With Separators and Labels",
  render: () => (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button variant="secondary" size="sm">
            Workflow <ChevronDownIcon size={14} />
          </Button>
        }
      />
      <DropdownMenuContent>
        <DropdownMenuGroup>
          <DropdownMenuLabel>Workflow</DropdownMenuLabel>
          <DropdownMenuItem>
            <PlayIcon size={14} />
            Run Now
          </DropdownMenuItem>
          <DropdownMenuItem>Schedule</DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuLabel>Edit</DropdownMenuLabel>
          <DropdownMenuItem>
            <CopyIcon size={14} />
            Duplicate
          </DropdownMenuItem>
          <DropdownMenuItem>
            <PencilIcon size={14} />
            Rename
          </DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive">
          <TrashIcon size={14} />
          Delete Workflow
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  ),
};

export const WithDangerItem: Story = {
  name: "With Danger Item",
  render: () => (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button variant="secondary" size="sm">
            More <ChevronDownIcon size={14} />
          </Button>
        }
      />
      <DropdownMenuContent>
        <DropdownMenuItem>Profile</DropdownMenuItem>
        <DropdownMenuItem>API Keys</DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive">Sign Out</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  ),
};

export const WithShortcuts: Story = {
  name: "With Keyboard Shortcuts",
  render: () => (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button variant="secondary" size="sm">
            Actions <ChevronDownIcon size={14} />
          </Button>
        }
      />
      <DropdownMenuContent>
        <DropdownMenuGroup>
          <DropdownMenuLabel>Actions</DropdownMenuLabel>
          <DropdownMenuItem>
            Run Workflow
            <DropdownMenuShortcut>⌘R</DropdownMenuShortcut>
          </DropdownMenuItem>
          <DropdownMenuItem>
            Open Canvas
            <DropdownMenuShortcut>⌘K</DropdownMenuShortcut>
          </DropdownMenuItem>
          <DropdownMenuItem>
            Commit Changes
            <DropdownMenuShortcut>⌘G</DropdownMenuShortcut>
          </DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive">Delete Workflow</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  ),
};
