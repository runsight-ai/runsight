import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import {
  Command,
  CommandInput,
  CommandList,
  CommandGroup,
  CommandItem,
  CommandShortcut,
  CommandSeparator,
  CommandEmpty,
} from "@/components/ui/command";

type CommandStoryArgs = { placeholder: string }

const meta: Meta<CommandStoryArgs> = {
  title: "Overlays/Command",
  parameters: { layout: "centered" },
  argTypes: {
    placeholder: {
      control: { type: "text" },
      description: "Placeholder text shown in the command input",
    },
  },
};
export default meta;

type Story = StoryObj<CommandStoryArgs>;

export const Default: Story = {
  name: "Default (controls)",
  args: {
    placeholder: "Search commands...",
  },
  render: (args) => (
    <div style={{ width: "480px" }}>
      <Command>
        <CommandInput placeholder={args.placeholder} />
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

export const WithGroups: Story = {
  name: "With Groups",
  render: () => (
    <div style={{ width: "480px" }}>
      <Command>
        <CommandInput placeholder="Type a command or search..." />
        <CommandList>
          <CommandEmpty>No results found.</CommandEmpty>
          <CommandGroup heading="Recent">
            <CommandItem>agent-pipeline-v2</CommandItem>
            <CommandItem>data-enrichment-flow</CommandItem>
            <CommandItem>customer-onboarding</CommandItem>
          </CommandGroup>
          <CommandSeparator />
          <CommandGroup heading="All Workflows">
            <CommandItem>support-triage</CommandItem>
            <CommandItem>document-review</CommandItem>
            <CommandItem>email-classifier</CommandItem>
          </CommandGroup>
        </CommandList>
      </Command>
    </div>
  ),
};

export const WithShortcuts: Story = {
  name: "With Keyboard Shortcuts",
  render: () => (
    <div style={{ width: "480px" }}>
      <Command>
        <CommandInput placeholder="Type a command or search..." />
        <CommandList>
          <CommandEmpty>No results found.</CommandEmpty>
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
