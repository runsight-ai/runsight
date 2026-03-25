import type { Meta, StoryObj } from "@storybook/react"
import React from "react"

import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableMonoCell,
  TableRow,
} from "@/components/ui/table"

const meta: Meta<typeof Table> = {
  title: "Data Display/Table",
  component: Table,
  parameters: {
    layout: "padded",
  },
}

export default meta

type Story = StoryObj<typeof Table>

// ---------------------------------------------------------------------------
// Default — basic data table
// ---------------------------------------------------------------------------

export const Default: Story = {
  render: () => (
    <Table>
      <TableCaption>Recent workflow runs</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead scope="col">Workflow</TableHead>
          <TableHead scope="col">Status</TableHead>
          <TableHead scope="col">Started</TableHead>
          <TableHead scope="col">Duration</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow>
          <TableCell>customer-support-triage</TableCell>
          <TableCell>Running</TableCell>
          <TableCell>2 min ago</TableCell>
          <TableCell>34s</TableCell>
        </TableRow>
        <TableRow>
          <TableCell>email-classifier</TableCell>
          <TableCell>Completed</TableCell>
          <TableCell>5 min ago</TableCell>
          <TableCell>12s</TableCell>
        </TableRow>
        <TableRow>
          <TableCell>data-pipeline</TableCell>
          <TableCell>Failed</TableCell>
          <TableCell>10 min ago</TableCell>
          <TableCell>1m 22s</TableCell>
        </TableRow>
      </TableBody>
    </Table>
  ),
}

// ---------------------------------------------------------------------------
// Mono — table with monospaced data cells (IDs, metrics, timestamps)
// ---------------------------------------------------------------------------

export const Mono: Story = {
  name: "Mono Values",
  render: () => (
    <Table>
      <TableCaption>Run IDs and metrics use monospaced font-mono cells</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead scope="col">Workflow</TableHead>
          <TableHead scope="col">Run ID</TableHead>
          <TableHead scope="col">Started</TableHead>
          <TableHead scope="col">Tokens</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow>
          <TableCell>customer-support-triage</TableCell>
          <TableMonoCell data-type="id">run_8f3k2m</TableMonoCell>
          <TableMonoCell data-type="timestamp">2026-03-25 09:14:00</TableMonoCell>
          <TableMonoCell data-type="metric">4,820</TableMonoCell>
        </TableRow>
        <TableRow>
          <TableCell>email-classifier</TableCell>
          <TableMonoCell data-type="id">run_9x1p4q</TableMonoCell>
          <TableMonoCell data-type="timestamp">2026-03-25 09:09:00</TableMonoCell>
          <TableMonoCell data-type="metric">1,204</TableMonoCell>
        </TableRow>
      </TableBody>
    </Table>
  ),
}

// ---------------------------------------------------------------------------
// Sortable Header — table with sortable column headers
// ---------------------------------------------------------------------------

export const SortableHeader: Story = {
  name: "Sortable Header",
  render: () => (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead scope="col" aria-sort="none">
            Workflow ↕
          </TableHead>
          <TableHead scope="col" aria-sort="descending">
            Started ↓
          </TableHead>
          <TableHead scope="col" aria-sort="none">
            Duration ↕
          </TableHead>
          <TableHead scope="col">Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow>
          <TableCell>customer-support-triage</TableCell>
          <TableMonoCell data-type="timestamp">2026-03-25 09:14:00</TableMonoCell>
          <TableMonoCell data-type="metric">34s</TableMonoCell>
          <TableCell>Running</TableCell>
        </TableRow>
        <TableRow>
          <TableCell>email-classifier</TableCell>
          <TableMonoCell data-type="timestamp">2026-03-25 09:09:00</TableMonoCell>
          <TableMonoCell data-type="metric">12s</TableMonoCell>
          <TableCell>Completed</TableCell>
        </TableRow>
      </TableBody>
    </Table>
  ),
}
