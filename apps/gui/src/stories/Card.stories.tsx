import type { Meta, StoryObj } from "@storybook/react";
import React from "react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
  CardDescription,
  CardAction,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const meta = {
  title: "Data Display/Card",
  parameters: { layout: "padded" },
};
export default meta;

type Story = StoryObj;

export const Default: Story = {
  render: () => (
    <Card style={{ maxWidth: "360px" }}>
      <CardContent>
        <p>A simple card with content and no header.</p>
      </CardContent>
    </Card>
  ),
};

export const WithHeader: Story = {
  name: "With Header",
  render: () => (
    <Card style={{ maxWidth: "360px" }}>
      <CardHeader>
        <CardTitle>Active Workflows</CardTitle>
        <CardDescription>
          Workflows currently running in your workspace.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p>12 workflows are currently active.</p>
      </CardContent>
    </Card>
  ),
};

export const WithHeaderAndAction: Story = {
  name: "With Header and Action",
  render: () => (
    <Card style={{ maxWidth: "360px" }}>
      <CardHeader>
        <CardTitle>Workflow Overview</CardTitle>
        <CardDescription>Summary of your most recent runs.</CardDescription>
        <CardAction>
          <Button variant="ghost" size="xs">
            View all
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        <p>3 completed, 1 running, 0 failed.</p>
      </CardContent>
      <CardFooter>
        <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
          Updated 2 min ago
        </span>
      </CardFooter>
    </Card>
  ),
};

export const Raised: Story = {
  name: "Raised",
  render: () => (
    <Card raised style={{ maxWidth: "360px" }}>
      <CardHeader>
        <CardTitle>Raised Card</CardTitle>
      </CardHeader>
      <CardContent>
        <p>Elevated surface with subtle shadow lift.</p>
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
      </CardHeader>
      <CardContent>
        <p>Hover to see the interactive state.</p>
      </CardContent>
    </Card>
  ),
};
