import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

import { Pagination } from "../components/ui/pagination";

const meta: Meta<typeof Pagination> = {
  title: "Navigation/Pagination",
  component: Pagination,
  parameters: { layout: "centered" },
  argTypes: {
    page: {
      control: { type: "number", min: 1 },
      description: "Current page (1-based)",
    },
    totalPages: {
      control: { type: "number", min: 1 },
      description: "Total number of pages",
    },
    pageSize: {
      control: { type: "number", min: 1 },
      description: "Items per page — used for range display",
    },
    total: {
      control: { type: "number", min: 0 },
      description: "Total item count — used for range display like '1-10 of 100'",
    },
    onPageChange: {
      action: "onPageChange",
      description: "Callback fired when a page button is clicked",
    },
  },
};
export default meta;

type Story = StoryObj<typeof Pagination>;

export const Default: Story = {
  name: "Default (controls)",
  args: {
    page: 1,
    totalPages: 10,
    pageSize: 10,
    total: undefined,
  },
};

export const ManyPages: Story = {
  name: "Many Pages",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)", alignItems: "center" }}>
      <Pagination page={1} totalPages={20} />
      <Pagination page={5} totalPages={20} />
      <Pagination page={10} totalPages={20} />
      <Pagination page={20} totalPages={20} />
    </div>
  ),
};

export const WithInfo: Story = {
  name: "With Info (.pagination__info)",
  render: () => (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)", alignItems: "center" }}>
      {/* .pagination__info renders "1-25 of 847" when total prop is supplied */}
      <Pagination
        page={1}
        totalPages={34}
        pageSize={25}
        total={847}
      />
      <Pagination
        page={2}
        totalPages={34}
        pageSize={25}
        total={847}
      />
      <Pagination
        page={10}
        totalPages={34}
        pageSize={25}
        total={847}
      />
    </div>
  ),
};
