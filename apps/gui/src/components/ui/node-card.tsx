// Design system tokens: block-agent, block-logic, block-control, block-utility, block-custom,
// surface-secondary, surface-selected, border-subtle, border-accent, radius-lg,
// text-heading, font-size-sm, font-mono, font-size-2xs,
// accent-9, success-7, danger-7, neutral-6, interactive-default

import * as React from "react"

import { cn } from "@/utils/helpers"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type BlockCategory =
  | "block-agent"
  | "block-logic"
  | "block-control"
  | "block-utility"
  | "block-custom"

export type ExecutionState =
  | "idle"
  | "running"
  | "success"
  | "error"
  | "skipped"

// ---------------------------------------------------------------------------
// Token maps
// ---------------------------------------------------------------------------

/** Top 3px stripe — one colour per block category */
const categoryStripeMap: Record<BlockCategory, string> = {
  "block-agent":   "bg-block-agent",
  "block-logic":   "bg-block-logic",
  "block-control": "bg-block-control",
  "block-utility": "bg-block-utility",
  "block-custom":  "bg-block-custom",
}

/** Left 2px execution-state indicator */
const executionStateMap: Record<ExecutionState, string> = {
  idle:    "bg-transparent",
  running: "bg-accent-9",
  success: "bg-success-7",
  error:   "bg-danger-7",
  skipped: "bg-neutral-6",
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface NodeCardProps extends Omit<React.ComponentProps<"div">, "title"> {
  /** Node display label shown in the header */
  title: string
  /** Block category determines the top stripe colour */
  category?: BlockCategory
  /** Current execution state (affects left border indicator) */
  executionState?: ExecutionState
  /** Whether the node is currently selected on the canvas */
  selected?: boolean
  /** Optional cost display (e.g. "$0.0024") rendered in font-mono */
  cost?: string
  /** Port slot rendered on the left side of the card (input handles) */
  inputPort?: React.ReactNode
  /** Port slot rendered on the right side of the card (output handles) */
  outputPort?: React.ReactNode
  /** Optional icon shown in the header alongside the title */
  icon?: React.ReactNode
  /** Body content */
  children?: React.ReactNode
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function NodeCard({
  title,
  category = "block-agent",
  executionState = "idle",
  selected = false,
  cost,
  inputPort,
  outputPort,
  icon,
  children,
  className,
  ...props
}: NodeCardProps) {
  return (
    <div
      data-slot="node-card"
      data-category={category}
      data-execution-state={executionState}
      data-selected={selected || undefined}
      className={cn(
        // Base shape & surface
        "relative flex flex-col overflow-hidden rounded-radius-lg",
        "border bg-surface-secondary",
        // Default border vs selected border
        selected
          ? "border-border-accent bg-surface-selected"
          : "border-border-subtle",
        className
      )}
      {...props}
    >
      {/* ---------------------------------------------------------------- */}
      {/* Top 3px category stripe                                           */}
      {/* ---------------------------------------------------------------- */}
      <span
        aria-hidden="true"
        data-slot="node-card-stripe"
        className={cn(
          "absolute inset-x-0 top-0 h-[3px]",
          categoryStripeMap[category]
        )}
      />

      {/* ---------------------------------------------------------------- */}
      {/* Left 2px execution-state bar                                      */}
      {/* ---------------------------------------------------------------- */}
      <span
        aria-hidden="true"
        data-slot="node-card-state-bar"
        className={cn(
          "absolute inset-y-0 left-0 w-[2px]",
          executionStateMap[executionState]
        )}
      />

      {/* ---------------------------------------------------------------- */}
      {/* Header                                                            */}
      {/* ---------------------------------------------------------------- */}
      <div
        data-slot="node-card-header"
        className="flex items-center gap-space-2 px-space-3 pb-space-2 pt-space-4"
      >
        {icon && (
          <span
            aria-hidden="true"
            data-slot="node-card-icon"
            className="shrink-0 text-muted"
          >
            {icon}
          </span>
        )}

        <span
          data-slot="node-card-title"
          className="min-w-0 flex-1 truncate text-font-size-sm font-medium text-heading"
        >
          {title}
        </span>

        {cost && (
          <span
            data-slot="node-card-cost"
            className="shrink-0 font-mono text-font-size-2xs text-muted"
          >
            {cost}
          </span>
        )}
      </div>

      {/* ---------------------------------------------------------------- */}
      {/* Body (optional children)                                          */}
      {/* ---------------------------------------------------------------- */}
      {children && (
        <div
          data-slot="node-card-body"
          className="px-space-3 pb-space-3"
        >
          {children}
        </div>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* Port handles (decorative — not tied to ReactFlow internals)       */}
      {/* ---------------------------------------------------------------- */}
      {inputPort && (
        <div
          data-slot="node-card-input-port"
          className="absolute left-0 top-1/2 -translate-x-1/2 -translate-y-1/2"
        >
          <span
            data-slot="node-card-port"
            className="block size-2.5 rounded-full border-2 border-interactive-default bg-surface-secondary"
          />
          {inputPort}
        </div>
      )}

      {outputPort && (
        <div
          data-slot="node-card-output-port"
          className="absolute right-0 top-1/2 -translate-x-1/2 -translate-y-1/2"
        >
          <span
            data-slot="node-card-port"
            className="block size-2.5 rounded-full border-2 border-interactive-default bg-surface-secondary"
          />
          {outputPort}
        </div>
      )}
    </div>
  )
}
