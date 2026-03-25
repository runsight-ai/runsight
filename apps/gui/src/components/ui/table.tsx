// Design system tokens used by BEM classes in components.css:
//   .table th  — background: var(--surface-secondary); color: var(--text-secondary) (text-muted);
//                font-size: var(--font-size-xs); text-transform: uppercase;
//                font-family: var(--font-mono); border-bottom: var(--border-subtle)
//   .table td  — border-bottom: var(--border-subtle); padding density: var(--density-cell-padding-block)
//   .table tbody tr:hover — background: var(--surface-hover)
//   .table tbody tr[aria-selected="true"] — background: var(--surface-selected)
//   .table td[data-type="data|metric|id|timestamp"] — font-family: var(--font-mono)
//   .table__empty — text-align: center; color: var(--text-muted)

import * as React from "react"

import { cn } from "@/utils/helpers"

function Table({ className, ...props }: React.ComponentProps<"table">) {
  return (
    <div
      data-slot="table-container"
      className="relative w-full overflow-x-auto"
    >
      <table
        data-slot="table"
        className={cn("table", className)}
        {...props}
      />
    </div>
  )
}

function TableHeader({ className, ...props }: React.ComponentProps<"thead">) {
  return (
    <thead
      data-slot="table-header"
      className={cn("table__head", className)}
      {...props}
    />
  )
}

function TableBody({ className, ...props }: React.ComponentProps<"tbody">) {
  return (
    <tbody
      data-slot="table-body"
      className={cn("table__body", className)}
      {...props}
    />
  )
}

function TableFooter({ className, ...props }: React.ComponentProps<"tfoot">) {
  return (
    <tfoot
      data-slot="table-footer"
      className={cn(className)}
      {...props}
    />
  )
}

function TableRow({ className, ...props }: React.ComponentProps<"tr">) {
  return (
    <tr
      data-slot="table-row"
      className={cn("table__row", className)}
      {...props}
    />
  )
}

function TableHead({ className, ...props }: React.ComponentProps<"th">) {
  return (
    <th
      data-slot="table-head"
      className={cn("table__header", className)}
      {...props}
    />
  )
}

function TableCell({ className, ...props }: React.ComponentProps<"td">) {
  return (
    <td
      data-slot="table-cell"
      className={cn("table__cell", className)}
      {...props}
    />
  )
}

// TableMonoCell: for data/metric/id/timestamp values — uses data-type="data" for mono styling
function TableMonoCell({ className, ...props }: React.ComponentProps<"td">) {
  return (
    <td
      data-slot="table-mono-cell"
      data-type="data"
      className={cn("table__cell table__cell--mono", className)}
      {...props}
    />
  )
}

function TableCaption({
  className,
  ...props
}: React.ComponentProps<"caption">) {
  return (
    <caption
      data-slot="table-caption"
      className={cn("mt-4 text-font-size-sm text-muted", className)}
      {...props}
    />
  )
}

export {
  Table,
  TableHeader,
  TableBody,
  TableFooter,
  TableHead,
  TableRow,
  TableCell,
  TableMonoCell,
  TableCaption,
}
