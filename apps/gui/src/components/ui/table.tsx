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
        className={cn("w-full border-collapse text-md", className)}
        {...props}
      />
    </div>
  )
}

function TableHeader({ className, ...props }: React.ComponentProps<"thead">) {
  return (
    <thead
      data-slot="table-header"
      className={cn(className)}
      {...props}
    />
  )
}

function TableBody({ className, ...props }: React.ComponentProps<"tbody">) {
  return (
    <tbody
      data-slot="table-body"
      className={cn(className)}
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
      className={cn(
        "transition-colors duration-[var(--duration-50,50ms)]",
        "hover:bg-surface-hover",
        "aria-selected:bg-surface-selected",
        "focus-visible:outline-[length:var(--focus-ring-width)] focus-visible:outline-[var(--focus-ring-color)] focus-visible:-outline-offset-1",
        className
      )}
      {...props}
    />
  )
}

function TableHead({ className, ...props }: React.ComponentProps<"th">) {
  return (
    <th
      data-slot="table-head"
      className={cn(
        // font + text
        "font-mono text-2xs font-medium tracking-wider uppercase text-muted text-left",
        // layout
        "px-3 py-[var(--density-cell-padding-block,8px)]",
        // border + bg
        "border-b border-border-default",
        "sticky top-0 bg-surface-primary z-[var(--z-sticky,10)]",
        // sortable
        "[&[aria-sort]]:cursor-pointer [&[aria-sort]]:select-none",
        "[&[aria-sort]:hover]:text-primary",
        "[&[aria-sort='ascending']]:after:content-['_↑']",
        "[&[aria-sort='descending']]:after:content-['_↓']",
        className
      )}
      {...props}
    />
  )
}

function TableCell({ className, ...props }: React.ComponentProps<"td">) {
  return (
    <td
      data-slot="table-cell"
      className={cn(
        "px-3 py-[var(--density-cell-padding-block,8px)]",
        "border-b border-border-subtle text-primary align-middle",
        // mono for data-type cells
        "[&[data-type='data']]:font-mono [&[data-type='data']]:text-sm",
        "[&[data-type='metric']]:font-mono [&[data-type='metric']]:text-sm",
        "[&[data-type='id']]:font-mono [&[data-type='id']]:text-sm",
        "[&[data-type='timestamp']]:font-mono [&[data-type='timestamp']]:text-sm",
        className
      )}
      {...props}
    />
  )
}

// TableMonoCell: for data/metric/id/timestamp values
function TableMonoCell({ className, ...props }: React.ComponentProps<"td">) {
  return (
    <td
      data-slot="table-mono-cell"
      data-type="data"
      className={cn(
        "px-3 py-[var(--density-cell-padding-block,8px)]",
        "border-b border-border-subtle text-primary align-middle",
        "font-mono text-sm",
        className
      )}
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
      className={cn("mt-4 text-sm text-muted", className)}
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
