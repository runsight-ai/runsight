// Design system tokens used by this component:
// Category stripes:  block-agent, block-logic, block-control, block-utility, block-custom
// Card surface:      surface-secondary, border-subtle, radius-lg
// Selected state:    border-accent, surface-selected
// Header text:       text-heading, font-size-sm
// Cost badge:        font-mono, font-size-2xs
// Execution states:  accent-9 (running), success-7 (success), danger-7 (error), neutral-6 (skipped)
// Port handles:      interactive-default

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

/**
 * Maps BlockCategory prop values to the data-category attribute values
 * expected by the .node-card BEM CSS (strips the "block-" prefix).
 */
const categoryDataAttrMap: Record<BlockCategory, string> = {
  "block-agent":   "agent",
  "block-logic":   "logic",
  "block-control": "control",
  "block-utility": "utility",
  "block-custom":  "custom",
}

/**
 * Maps ExecutionState prop values to data-state attribute values used by BEM CSS.
 * idle / skipped have no BEM state override — omit attribute.
 */
const executionStateDataAttrMap: Record<ExecutionState, string | undefined> = {
  idle:    undefined,
  running: "running",
  success: "completed",
  error:   "failed",
  skipped: undefined,
}

/**
 * Left 2px execution-state indicator.
 * Maps to design system color tokens: accent-9, success-7, danger-7, neutral-6.
 */
const executionStateBarMap: Record<ExecutionState, string> = {
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
  const dataCategory = categoryDataAttrMap[category]
  const dataState = executionStateDataAttrMap[executionState]

  return (
    // .node-card BEM root:
    //   background: surface-secondary  border: border-subtle  radius: radius-lg
    //   data-category drives border-top color (block-agent / block-logic / etc.)
    //   aria-selected="true" drives border-accent + surface-selected selected state
    //   data-state drives execution-state overrides
    <div
      data-slot="node-card"
      data-category={dataCategory}
      data-state={dataState}
      aria-selected={selected || undefined}
      className={cn("node-card", className)}
      {...props}
    >
      {/* ---------------------------------------------------------------- */}
      {/* Left 2px execution-state bar                                      */}
      {/* accent-9 / success-7 / danger-7 / neutral-6                      */}
      {/* ---------------------------------------------------------------- */}
      <span
        aria-hidden="true"
        data-slot="node-card-state-bar"
        className={cn(
          "absolute inset-y-0 left-0 w-[2px]",
          executionStateBarMap[executionState]
        )}
      />

      {/* ---------------------------------------------------------------- */}
      {/* Header: .node-card__header                                        */}
      {/* title: text-heading + font-size-sm via .node-card__name          */}
      {/* ---------------------------------------------------------------- */}
      <div
        data-slot="node-card-header"
        className="node-card__header"
      >
        {icon && (
          // .node-card__icon — color driven by category / state via CSS
          <span
            aria-hidden="true"
            data-slot="node-card-icon"
            className="node-card__icon"
          >
            {icon}
          </span>
        )}

        {/* .node-card__name — text-heading + font-size-sm */}
        <span
          data-slot="node-card-title"
          className="node-card__name"
        >
          {title}
        </span>

        {/* .node-card__cost-badge — font-mono + font-size-2xs */}
        {cost && (
          <span
            data-slot="node-card-cost"
            className="node-card__cost-badge"
          >
            {cost}
          </span>
        )}
      </div>

      {/* ---------------------------------------------------------------- */}
      {/* Body (optional children) — .node-card__body                      */}
      {/* ---------------------------------------------------------------- */}
      {children && (
        <div
          data-slot="node-card-body"
          className="node-card__body"
        >
          {children}
        </div>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* Port handles — .node-card__port + .node-card__port--input/output  */}
      {/* interactive-default applied on hover via BEM CSS                  */}
      {/* ---------------------------------------------------------------- */}
      {inputPort && (
        <div data-slot="node-card-input-port">
          <span
            data-slot="node-card-port"
            className="node-card__port node-card__port--input"
          />
          {inputPort}
        </div>
      )}

      {outputPort && (
        <div data-slot="node-card-output-port">
          <span
            data-slot="node-card-port"
            className="node-card__port node-card__port--output"
          />
          {outputPort}
        </div>
      )}
    </div>
  )
}
