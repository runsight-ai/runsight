// Design system tokens used by this component:
// Category stripes:  block-agent, block-logic, block-control, block-utility, block-custom
// Card surface:      surface-secondary, border-subtle, radius-lg
// Selected state:    border-accent, surface-selected
// Header text:       text-heading, font-size-sm
// Cost badge:        font-mono, font-size-2xs
// Execution states:  accent-9 (running), success-7 (success), danger-7 (error), neutral-6 (skipped)
// Port handles:      interactive-default
// Soul avatars:      .node-card__avatar-stack, .node-card__avatar, .soul-tip-wrap, .soul-tip
// Meta row:          .node-card__meta, .node-card__meta-sep
// Port rows:         .node-card__port-rows, .node-card__port-row, .node-card__port-row-name,
//                    .node-card__port-row-dot, .node-card__port-row-dot--pass/fail
// Status badge:      .node-card__status-badge (hidden by default, used for running/completed/failed)

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

/** A named output port row rendered inside .node-card__port-rows */
export interface NodeCardPort {
  /** Port name shown in monospace uppercase (e.g. "pass", "fail", "market") */
  name: string
  /** Port type drives .node-card__port-row-dot BEM modifier colour */
  type?: "pass" | "fail" | "default"
}

/** Soul assignment shown as a coloured avatar with tooltip in .node-card__avatar-stack */
export interface NodeCardSoul {
  /** Single uppercase letter(s) for the avatar (e.g. "W", "TL") */
  initial: string
  /** HSL or hex background for the avatar circle and tooltip dot */
  color: string
  /** Soul name (e.g. "writer_main") */
  name: string
  /** Model identifier (e.g. "gpt-4o") */
  model?: string
  /** Provider name (e.g. "OpenAI") */
  provider?: string
  /** Optional prompt preview (clamped to 2 lines in the tooltip) */
  prompt?: string
  /** Additional key/value rows to show in the tooltip */
  rows?: Array<{ key: string; val: string }>
}

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
  /** Whether to render the .node-card__port--input handle on the left edge */
  inputPort?: boolean
  /** Whether to render the .node-card__port--output handle on the right edge */
  outputPort?: boolean
  /** Named output port rows — renders .node-card__port-rows */
  ports?: NodeCardPort[]
  /** Soul assignments — renders .node-card__avatar-stack with tooltip */
  souls?: NodeCardSoul[]
  /** Status badge text (e.g. "Running") — renders .node-card__status-badge */
  statusBadge?: string
  /** Meta label(s) shown below the header row in uppercase monospace */
  meta?: string | string[]
  /** Optional icon shown in the header alongside the title */
  icon?: React.ReactNode
  /** Body content (only used when no souls/meta) */
  children?: React.ReactNode
}

// ---------------------------------------------------------------------------
// SoulAvatar sub-component — .soul-tip-wrap > .node-card__avatar + .soul-tip
// ---------------------------------------------------------------------------

function SoulAvatar({ soul }: { soul: NodeCardSoul }) {
  const rows: Array<{ key: string; val: string }> = [
    ...(soul.model ? [{ key: "Model", val: soul.model }] : []),
    ...(soul.provider ? [{ key: "Provider", val: soul.provider }] : []),
    ...(soul.rows ?? []),
  ]

  return (
    <span className="soul-tip-wrap">
      <span
        className="node-card__avatar"
        style={{ background: soul.color }}
      >
        {soul.initial}
      </span>
      <span className="soul-tip">
        <span className="soul-tip__name">
          <span className="soul-tip__dot" style={{ background: soul.color }} />
          {soul.name}
        </span>
        {rows.map(({ key, val }) => (
          <span key={key} className="soul-tip__row">
            <span className="soul-tip__key">{key}</span>
            <span className="soul-tip__val">{val}</span>
          </span>
        ))}
        {soul.prompt && (
          <span className="soul-tip__prompt">{soul.prompt}</span>
        )}
      </span>
    </span>
  )
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
  inputPort = false,
  outputPort = false,
  ports,
  souls,
  statusBadge,
  meta,
  icon,
  children,
  className,
  ...props
}: NodeCardProps) {
  const dataCategory = categoryDataAttrMap[category]
  const dataState = executionStateDataAttrMap[executionState]

  // Normalise meta to array for rendering
  const metaItems = meta
    ? Array.isArray(meta) ? meta : [meta]
    : undefined

  // Status badge BEM modifier derives from executionState when statusBadge text is provided
  const statusBadgeModifier =
    executionState === "running" ? "running"
    : executionState === "success" ? "completed"
    : executionState === "error" ? "failed"
    : undefined

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
      {/* Input port handle — .node-card__port--input (left edge)          */}
      {/* ---------------------------------------------------------------- */}
      {inputPort && (
        <div
          data-slot="node-card-port"
          className="node-card__port node-card__port--input"
        />
      )}

      {/* ---------------------------------------------------------------- */}
      {/* Status badge — .node-card__status-badge (hidden by CSS default)  */}
      {/* ---------------------------------------------------------------- */}
      {statusBadge && (
        <div
          data-slot="node-card-status-badge"
          className={cn(
            "node-card__status-badge",
            statusBadgeModifier && `node-card__status-badge--${statusBadgeModifier}`
          )}
        >
          {statusBadge}
        </div>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* Header: .node-card__header                                        */}
      {/* icon + name + avatar-stack                                        */}
      {/* ---------------------------------------------------------------- */}
      <div
        data-slot="node-card-header"
        className="node-card__header"
      >
        {icon && (
          // .node-card__icon — color driven by category / state via CSS
          <div
            aria-hidden="true"
            data-slot="node-card-icon"
            className="node-card__icon"
          >
            {icon}
          </div>
        )}

        {/* .node-card__name — text-heading + font-size-sm */}
        <span
          data-slot="node-card-title"
          className="node-card__name"
        >
          {title}
        </span>

        {/* .node-card__avatar-stack — soul avatar circles with tooltips */}
        {souls && souls.length > 0 && (
          <div
            data-slot="node-card-avatar-stack"
            className="node-card__avatar-stack"
          >
            {souls.map((soul, idx) => (
              <SoulAvatar key={idx} soul={soul} />
            ))}
          </div>
        )}
      </div>

      {/* ---------------------------------------------------------------- */}
      {/* Meta row — .node-card__meta                                       */}
      {/* uppercase monospace accent label (e.g. "Linear · 2 ports")       */}
      {/* ---------------------------------------------------------------- */}
      {metaItems && (
        <div
          data-slot="node-card-meta"
          className="node-card__meta"
        >
          {metaItems.map((item, idx) => (
            <React.Fragment key={idx}>
              {idx > 0 && (
                <span className="node-card__meta-sep">&middot;</span>
              )}
              <span>{item}</span>
            </React.Fragment>
          ))}
        </div>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* Body (optional children) — .node-card__body                      */}
      {/* Only used when no souls/meta present                              */}
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
      {/* Named port rows — .node-card__port-rows                          */}
      {/* Renders conditional output port dots (pass/fail/default)         */}
      {/* ---------------------------------------------------------------- */}
      {ports && ports.length > 0 && (
        <div
          data-slot="node-card-port-rows"
          className="node-card__port-rows"
        >
          {ports.map((port, idx) => (
            <div key={idx} className="node-card__port-row">
              <span className="node-card__port-row-name">{port.name}</span>
              <div
                className={cn(
                  "node-card__port-row-dot",
                  port.type === "pass" && "node-card__port-row-dot--pass",
                  port.type === "fail" && "node-card__port-row-dot--fail"
                )}
              />
            </div>
          ))}
        </div>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* Cost badge — .node-card__cost-badge (positioned bottom-right)    */}
      {/* ---------------------------------------------------------------- */}
      {cost && (
        <div
          data-slot="node-card-cost"
          className="node-card__cost-badge"
        >
          {cost}
        </div>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* Output port handle — .node-card__port--output (right edge)       */}
      {/* ---------------------------------------------------------------- */}
      {outputPort && (
        <div
          data-slot="node-card-port"
          className="node-card__port node-card__port--output"
        />
      )}
    </div>
  )
}
