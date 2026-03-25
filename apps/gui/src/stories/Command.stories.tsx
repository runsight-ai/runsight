import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command";

const meta: Meta = {
  title: "Overlays/Command",
  parameters: {
    layout: "centered",
  },
};

export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <div className="w-[480px]">
      <Command>
        <CommandInput placeholder="Search commands..." />
        <CommandList>
          <CommandEmpty>No results found.</CommandEmpty>
          <CommandGroup heading="Workflows">
            <CommandItem>New Workflow</CommandItem>
            <CommandItem>Open Workflow</CommandItem>
            <CommandItem>Clone Workflow</CommandItem>
          </CommandGroup>
          <CommandGroup heading="Souls">
            <CommandItem>New Soul</CommandItem>
            <CommandItem>Edit Soul</CommandItem>
          </CommandGroup>
        </CommandList>
      </Command>
    </div>
  ),
};

export const WithShortcuts: Story = {
  name: "With Keyboard Shortcuts",
  render: () => (
    <div className="w-[480px]">
      <Command>
        <CommandInput placeholder="Type a command or search..." />
        <CommandList>
          <CommandEmpty>No commands found.</CommandEmpty>
          <CommandGroup heading="Actions">
            <CommandItem>
              Run Workflow
              <CommandShortcut>⌘R</CommandShortcut>
            </CommandItem>
            <CommandItem>
              Open Canvas
              <CommandShortcut>⌘K</CommandShortcut>
            </CommandItem>
            <CommandItem>
              Commit Changes
              <CommandShortcut>⌘G</CommandShortcut>
            </CommandItem>
            <CommandItem>
              Deploy
              <CommandShortcut>⌘⇧D</CommandShortcut>
            </CommandItem>
          </CommandGroup>
          <CommandSeparator />
          <CommandGroup heading="Navigation">
            <CommandItem>
              Go to Runs
              <CommandShortcut>⌘1</CommandShortcut>
            </CommandItem>
            <CommandItem>
              Go to Workflows
              <CommandShortcut>⌘2</CommandShortcut>
            </CommandItem>
            <CommandItem>
              Go to Settings
              <CommandShortcut>⌘,</CommandShortcut>
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </Command>
    </div>
  ),
};

export const Basic: Story = {
  render: () => (
    <div className="w-[400px]">
      <Command>
        <CommandInput placeholder="Search..." />
        <CommandList>
          <CommandEmpty>No results.</CommandEmpty>
          <CommandGroup heading="Recent">
            <CommandItem>agent-pipeline-v2</CommandItem>
            <CommandItem>data-enrichment-flow</CommandItem>
            <CommandItem>customer-onboarding</CommandItem>
          </CommandGroup>
        </CommandList>
      </Command>
    </div>
  ),
};
