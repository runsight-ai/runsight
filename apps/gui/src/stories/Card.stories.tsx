import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
  CardAction,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const meta: Meta<typeof Card> = {
  title: "Data Display/Card",
  component: Card,
  parameters: { layout: "padded" },
  argTypes: {
    raised: {
      control: { type: "boolean" },
      description: "Elevated surface with subtle box-shadow",
    },
    interactive: {
      control: { type: "boolean" },
      description: "Pointer cursor with hover border highlight",
    },
  },
};
export default meta;

type Story = StoryObj<typeof Card>;

export const Default: Story = {
  name: "Default (controls)",
  args: {
    raised: false,
    interactive: false,
  },
  render: (args) => (
    <Card {...args} style={{ maxWidth: "360px" }}>
      <CardHeader>
        <CardTitle>Workflow Overview</CardTitle>
        <CardDescription>Summary of your most recent runs.</CardDescription>
      </CardHeader>
      <CardContent>
        <p>3 completed, 1 running, 0 failed.</p>
      </CardContent>
    </Card>
  ),
};

export const Raised: Story = {
  name: "Raised",
  render: () => (
    <Card raised style={{ maxWidth: "360px" }}>
      <CardHeader>
        <CardTitle>Raised Card</CardTitle>
        <CardDescription>Elevated surface with subtle shadow lift.</CardDescription>
      </CardHeader>
      <CardContent>
        <p>Uses <code>card--raised</code> for elevated background and box-shadow.</p>
      </CardContent>
    </Card>
  ),
};

export const Interactive: Story = {
  name: "Interactive",
  render: () => (
    <Card interactive style={{ maxWidth: "360px" }} tabIndex={0}>
      <CardHeader>
        <CardTitle>Clickable Card</CardTitle>
        <CardDescription>Hover to see the interactive state.</CardDescription>
      </CardHeader>
      <CardContent>
        <p>Uses <code>card--interactive</code> for pointer cursor and hover border.</p>
      </CardContent>
    </Card>
  ),
};

export const WithFooter: Story = {
  name: "With Footer",
  render: () => (
    <Card style={{ maxWidth: "360px" }}>
      <CardHeader>
        <CardTitle>Active Workflows</CardTitle>
        <CardDescription>Workflows currently running in your workspace.</CardDescription>
        <CardAction>
          <Button variant="ghost" size="xs">View all</Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        <p>12 workflows are currently active.</p>
      </CardContent>
      <CardFooter>
        <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
          Updated 2 min ago
        </span>
      </CardFooter>
    </Card>
  ),
};
