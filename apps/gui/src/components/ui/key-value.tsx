import * as React from "react"

import { cn } from "@/utils/helpers"

// Design spec:
// Container: grid 2-col (minmax(100px, auto) 1fr), gap row=space-1(4px) col=space-4(16px), text-md
// Key cell:  text-muted, text-sm, whitespace-nowrap
// Value cell: text-primary, font-mono, text-sm, break-all

interface KeyValueProps extends React.HTMLAttributes<HTMLDivElement> {
  /** The label (key column) */
  label: string
  /** The value (value column) */
  value: React.ReactNode
  /**
   * When true (default), the value is rendered in monospace font per DS spec.
   * Pass false to render in body font.
   */
  mono?: boolean
}

function KeyValue({
  className,
  label,
  value,
  mono = true,
  ...props
}: KeyValueProps) {
  return (
    <div
      data-slot="key-value"
      className={cn(
        "grid gap-x-4 gap-y-1 text-md",
        "[grid-template-columns:minmax(100px,auto)_1fr]",
        className
      )}
      {...props}
    >
      <span className="text-muted text-sm whitespace-nowrap">{label}</span>
      <span
        className={cn(
          "text-primary text-sm break-all",
          mono ? "font-mono" : "font-[var(--font-body)]"
        )}
      >
        {value}
      </span>
    </div>
  )
}

interface KeyValueListProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Array of { label, value, mono? } entries */
  items: Array<{ label: string; value: React.ReactNode; mono?: boolean }>
}

/**
 * KeyValueList — stacks multiple key-value pairs in a single shared grid,
 * so all keys and values align in the same two columns.
 */
function KeyValueList({
  className,
  items,
  ...props
}: KeyValueListProps) {
  return (
    <div
      data-slot="key-value-list"
      className={cn(
        "grid gap-x-4 gap-y-1 text-md",
        "[grid-template-columns:minmax(100px,auto)_1fr]",
        className
      )}
      {...props}
    >
      {items.map(({ label, value, mono = true }, i) => (
        <React.Fragment key={i}>
          <span className="text-muted text-sm whitespace-nowrap">{label}</span>
          <span
            className={cn(
              "text-primary text-sm break-all",
              mono ? "font-mono" : "font-[var(--font-body)]"
            )}
          >
            {value}
          </span>
        </React.Fragment>
      ))}
    </div>
  )
}

export { KeyValue, KeyValueList }
export type { KeyValueProps, KeyValueListProps }
