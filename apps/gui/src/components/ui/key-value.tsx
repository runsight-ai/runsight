import * as React from "react"

import { cn } from "@/utils/helpers"

// Design system tokens:
// .kv: grid 2-col (minmax(100px, auto) 1fr), gap space-1 space-4, font-size-md
// .kv__key: text-muted, font-size-sm, white-space nowrap
// .kv__value: text-primary, font-mono, font-size-sm, word-break break-all
//
// Note: CSS spec names the class .kv__value. The task brief calls it .kv__val —
// the actual CSS rule is .kv__value, which is what we apply here.
// The `mono` prop is a component-level boolean; the value cell already uses
// font-mono by default per the DS spec. When mono=false we override with font-body
// via inline style (no .kv--mono class exists in the CSS).

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
      className={cn("kv", className)}
      {...props}
    >
      <span className="kv__key">{label}</span>
      <span
        className="kv__value"
        style={mono ? undefined : { fontFamily: "var(--font-body)" }}
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
      className={cn("kv", className)}
      {...props}
    >
      {items.map(({ label, value, mono = true }, i) => (
        <React.Fragment key={i}>
          <span className="kv__key">{label}</span>
          <span
            className="kv__value"
            style={mono ? undefined : { fontFamily: "var(--font-body)" }}
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
