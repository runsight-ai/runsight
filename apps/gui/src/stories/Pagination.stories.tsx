import type { Meta, StoryObj } from "@storybook/react"
import React, { useState } from "react"

import { Pagination } from "@/components/ui/pagination"

const meta: Meta<typeof Pagination> = {
  title: "Navigation/Pagination",
  component: Pagination,
  parameters: {
    layout: "centered",
  },
}

export default meta

type Story = StoryObj<typeof Pagination>

export const Default: Story = {
  render: () => {
    const [page, setPage] = useState(1)
    return (
      <Pagination
        page={page}
        totalPages={10}
        onPageChange={setPage}
      />
    )
  },
}

export const Basic: Story = {
  render: () => {
    const [page, setPage] = useState(3)
    return (
      <Pagination
        page={page}
        totalPages={7}
        onPageChange={setPage}
      />
    )
  },
}

export const WithRangeDisplay: Story = {
  name: "With Range Display (of total)",
  render: () => {
    const [page, setPage] = useState(1)
    const pageSize = 10
    const total = 100
    return (
      <Pagination
        page={page}
        totalPages={Math.ceil(total / pageSize)}
        pageSize={pageSize}
        total={total}
        onPageChange={setPage}
      />
    )
  },
}

export const RangeCount: Story = {
  name: "Range Count — Large Dataset",
  render: () => {
    const [page, setPage] = useState(5)
    const pageSize = 25
    const total = 1250
    return (
      <Pagination
        page={page}
        totalPages={Math.ceil(total / pageSize)}
        pageSize={pageSize}
        total={total}
        onPageChange={setPage}
      />
    )
  },
}

export const FewPages: Story = {
  name: "Few Pages (no ellipsis)",
  render: () => {
    const [page, setPage] = useState(2)
    return (
      <Pagination
        page={page}
        totalPages={5}
        onPageChange={setPage}
      />
    )
  },
}

export const FirstPage: Story = {
  render: () => (
    <Pagination
      page={1}
      totalPages={10}
      pageSize={10}
      total={95}
    />
  ),
}

export const LastPage: Story = {
  render: () => (
    <Pagination
      page={10}
      totalPages={10}
      pageSize={10}
      total={95}
    />
  ),
}
