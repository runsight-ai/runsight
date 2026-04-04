import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { Badge, BadgeDot } from "../components/ui/badge";
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
  TableMonoCell,
} from "../components/ui/table";

const meta: Meta<typeof Table> = {
  title: "Data Display/Table",
  component: Table,
  parameters: { layout: "padded" },
};
export default meta;

type Story = StoryObj<typeof Table>;

export const Default: Story = {
  name: "Default",
  render: () => (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Workflow</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Started</TableHead>
          <TableHead>Duration</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow>
          <TableCell>customer-support-triage</TableCell>
          <TableCell>
            <Badge variant="success"><BadgeDot />Running</Badge>
          </TableCell>
          <TableCell>2 min ago</TableCell>
          <TableMonoCell>34s</TableMonoCell>
        </TableRow>
        <TableRow>
          <TableCell>email-classifier</TableCell>
          <TableCell>
            <Badge variant="neutral">Completed</Badge>
          </TableCell>
          <TableCell>5 min ago</TableCell>
          <TableMonoCell>12s</TableMonoCell>
        </TableRow>
        <TableRow>
          <TableCell>data-pipeline</TableCell>
          <TableCell>
            <Badge variant="danger">Failed</Badge>
          </TableCell>
          <TableCell>10 min ago</TableCell>
          <TableMonoCell>1m 22s</TableMonoCell>
        </TableRow>
      </TableBody>
    </Table>
  ),
};

export const WithSelection: Story = {
  name: "With Selection (aria-selected)",
  render: () => (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Workflow</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Started</TableHead>
          <TableHead>Duration</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow>
          <TableCell>customer-support-triage</TableCell>
          <TableCell>
            <Badge variant="success"><BadgeDot />Running</Badge>
          </TableCell>
          <TableCell>2 min ago</TableCell>
          <TableMonoCell>34s</TableMonoCell>
        </TableRow>
        <TableRow aria-selected="true">
          <TableCell>email-classifier</TableCell>
          <TableCell>
            <Badge variant="neutral">Completed</Badge>
          </TableCell>
          <TableCell>5 min ago</TableCell>
          <TableMonoCell>12s</TableMonoCell>
        </TableRow>
        <TableRow>
          <TableCell>data-pipeline</TableCell>
          <TableCell>
            <Badge variant="danger">Failed</Badge>
          </TableCell>
          <TableCell>10 min ago</TableCell>
          <TableMonoCell>1m 22s</TableMonoCell>
        </TableRow>
      </TableBody>
    </Table>
  ),
};

export const SortableHeaders: Story = {
  name: "Sortable Headers",
  render: () => (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead aria-sort="none">Workflow</TableHead>
          <TableHead aria-sort="descending">Started</TableHead>
          <TableHead aria-sort="none">Duration</TableHead>
          <TableHead>Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow>
          <TableCell>customer-support-triage</TableCell>
          <TableMonoCell>2026-03-25 09:14:00</TableMonoCell>
          <TableMonoCell>34s</TableMonoCell>
          <TableCell>
            <Badge variant="success"><BadgeDot />Running</Badge>
          </TableCell>
        </TableRow>
        <TableRow>
          <TableCell>email-classifier</TableCell>
          <TableMonoCell>2026-03-25 09:09:00</TableMonoCell>
          <TableMonoCell>12s</TableMonoCell>
          <TableCell>
            <Badge variant="neutral">Completed</Badge>
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>
  ),
};
