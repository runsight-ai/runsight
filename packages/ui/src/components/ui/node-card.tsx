// Design system tokens used by this component:
// Category stripes:  block-agent, block-logic, block-control, block-utility, block-custom
// Card surface:      surface-tertiary, neutral-4, radius-lg
// Selected state:    amber 38/92%/55% sides + glow
// Header text:       text-heading, 13px
// Cost badge:        font-mono, font-size-2xs, accent-themed
// Execution states:  accent-9 (running), success-9 (completed), danger-9 (failed/error)
// Port handles:      interactive-default
// Soul avatars:      inline Tailwind (no BEM)

import * as React from "react"

import { cn } from "../../utils/helpers"

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

/** A named output port row rendered inside the port-rows section */
export interface NodeCardPort {
  /** Port name shown in monospace uppercase (e.g. "pass", "fail", "market") */
  name: string
  /** Port type drives dot colour */
  type?: "pass" | "fail" | "default"
}

/** Soul assignment shown as a coloured avatar with tooltip */
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
// CVA variants
// ---------------------------------------------------------------------------

/** Top-stripe colour by category */
const categoryStripe: Record<BlockCategory, string> = {
  "block-agent":   "border-t-[var(--block-agent)]",
  "block-logic":   "border-t-[var(--block-logic)]",
  "block-control": "border-t-[var(--block-control)]",
  "block-utility": "border-t-[var(--block-utility)]",
  "block-custom":  "border-t-[var(--block-custom)]",
}

/** Icon colour by category */
const categoryIconColor: Record<BlockCategory, string> = {
  "block-agent":   "text-[var(--block-agent)]",
  "block-logic":   "text-[var(--block-logic)]",
  "block-control": "text-[var(--block-control)]",
  "block-utility": "text-[var(--block-utility)]",
  "block-custom":  "text-[var(--block-custom)]",
}

/** Icon colour override for execution states */
const stateIconColor: Partial<Record<ExecutionState, string>> = {
  running: "text-(--accent-11)",
  success: "text-(--success-9)",
  error:   "text-(--danger-9)",
}

// ---------------------------------------------------------------------------
// SoulAvatar sub-component
// Pure Tailwind — no BEM
// ---------------------------------------------------------------------------

function SoulAvatar({ soul }: { soul: NodeCardSoul }) {
  const rows: Array<{ key: string; val: string }> = [
    ...(soul.model ? [{ key: "Model", val: soul.model }] : []),
    ...(soul.provider ? [{ key: "Provider", val: soul.provider }] : []),
    ...(soul.rows ?? []),
  ]

  return (
    <span className="relative inline-flex group/soul-tip">
      {/* Avatar circle */}
      <span
        className={[
          "inline-flex items-center justify-center",
          "size-5 rounded-full flex-shrink-0", // icon-size-lg = 20px
          "text-3xs font-semibold text-on-accent leading-none",
          "shadow-[0_0_0_1px_color-mix(in_srgb,var(--neutral-6)_50%,transparent)]",
          "cursor-default select-none",
        ].join(" ")}
        style={{ background: soul.color }}
      >
        {soul.initial}
      </span>

      {/* Tooltip panel — opacity-driven, shown on group hover */}
      <span
        className={[
          "absolute bottom-[calc(100%+10px)] left-1/2 -translate-x-1/2",
          "w-[200px]", // soul-tip spec: 200px
          "bg-(--neutral-2) border border-(--neutral-4)",
          "rounded-[var(--radius-md)]",
          "px-3 py-2",
          "shadow-[0_8px_24px_var(--elevation-overlay-shadow)]",
          "font-mono text-3xs",
          "opacity-0 pointer-events-none",
          "transition-opacity duration-[var(--duration-100)]",
          "group-hover/soul-tip:opacity-100",
          "z-[var(--z-popover)]",
        ].join(" ")}
      >
        {/* Down-pointing caret */}
        <span
          className={[
            "absolute left-1/2 -translate-x-1/2 top-full",
            "w-0 h-0",
            "border-l-[6px] border-l-transparent",
            "border-r-[6px] border-r-transparent",
            "border-t-[6px] border-t-(--neutral-4)",
          ].join(" ")}
          aria-hidden="true"
        />

        {/* Name row */}
        <span className="flex items-center gap-1.5 mb-1.5">
          <span
            className="w-1.5 h-1.5 rounded-full flex-shrink-0"
            style={{ background: soul.color }}
          />
          <span className="text-3xs text-(--text-primary) font-medium">{soul.name}</span>
        </span>

        {/* Key/value rows */}
        {rows.map(({ key, val }) => (
          <span key={key} className="flex justify-between items-baseline mb-[3px]">
            <span className="text-(--text-muted) uppercase tracking-wider text-3xs">{key}</span>
            <span className="text-(--accent-11) font-mono text-3xs">{val}</span>
          </span>
        ))}

        {/* Prompt preview */}
        {soul.prompt && (
          <span className="block text-3xs text-(--text-muted) mt-1.5 leading-tight line-clamp-2">
            {soul.prompt}
          </span>
        )}
      </span>
    </span>
  )
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface NodeCardProps extends Omit<React.ComponentProps<"div">, "title"> {
  /** Node display label shown in the header */
  title: string
  /** Block category determines the top stripe colour */
  category?: BlockCategory
  /** Current execution state (affects top stripe + background + animation) */
  executionState?: ExecutionState
  /** Whether the node is currently selected on the canvas */
  selected?: boolean
  /** Optional cost display (e.g. "$0.0024") rendered in font-mono */
  cost?: string
  /** Whether to render the input port handle on the left edge */
  inputPort?: boolean
  /** Whether to render the output port handle on the right edge */
  outputPort?: boolean
  /** Named output port rows */
  ports?: NodeCardPort[]
  /** Soul assignment — renders an avatar with tooltip */
  soul?: NodeCardSoul
  /** Status badge text (hidden by CSS per spec; kept for a11y/data layer) */
  statusBadge?: string
  /** Meta label(s) shown below the header row in uppercase monospace */
  meta?: string | string[]
  /** Optional icon shown in the header alongside the title */
  icon?: React.ReactNode
  /** Body content (only used when no souls/meta) */
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
  inputPort = false,
  outputPort = false,
  ports,
  soul,
  statusBadge,
  meta,
  icon,
  children,
  className,
  ...props
}: NodeCardProps) {
  // Normalise meta to array
  const metaItems = meta
    ? Array.isArray(meta) ? meta : [meta]
    : undefined

  // Execution-state top stripe override
  const stateStripe: Partial<Record<ExecutionState, string>> = {
    running: "border-t-[var(--accent-9)]",
    success: "border-t-[var(--success-9)]",
    error:   "border-t-[var(--danger-9)]",
  }

  // Execution-state background tint
  const stateBg: Partial<Record<ExecutionState, string>> = {
    success: "bg-[color-mix(in_srgb,var(--success-9)_3%,transparent)]",
    error:   "bg-[color-mix(in_srgb,var(--danger-9)_4%,transparent)]",
  }

  // Selection border (amber sides + glow, preserves top stripe)
  const selectedClasses = selected
    ? [
        "border-l-accent-9/50",
        "border-r-accent-9/50",
        "border-b-accent-9/50",
        "shadow-[0_0_16px_color-mix(in_srgb,var(--accent-9)_15%,transparent)]",
      ].join(" ")
    : ""

  // Running pulse animation
  const runningAnimation = executionState === "running"
    ? "animate-[node-pulse-glow_2.5s_ease-in-out_infinite]"
    : ""

  // Resolve icon colour: state overrides category
  const iconColorClass =
    stateIconColor[executionState] ?? categoryIconColor[category] ?? "text-(--neutral-9)"

  // Top stripe: state overrides category
  const topStripeClass =
    stateStripe[executionState] ?? categoryStripe[category]

  return (
    <div
      data-slot="node-card"
      data-category={category}
      data-state={executionState}
      aria-selected={selected || undefined}
      className={cn(
        // base layout
        "relative w-[var(--node-card-width,260px)] cursor-pointer",
        // surface
        "bg-(--surface-tertiary)",
        // border: thin neutral on sides/bottom, 3px top stripe
        "border border-(--neutral-4) border-t-[3px]",
        // radius: flat top (stripe acts as top), rounded bottom
        "rounded-b-[var(--radius-lg)] rounded-t-none",
        // shadow + transition
        "shadow-card",
        "transition-[border-color,box-shadow] duration-150 ease-out",
        // hover
        "hover:border-(--border-hover) hover:shadow-card-hover",
        // top stripe colour (state > category)
        topStripeClass,
        // execution bg tint
        stateBg[executionState],
        // selected amber outline
        selectedClasses,
        // running glow animation
        runningAnimation,
        className
      )}
      {...props}
    >
      {/* Input port handle — left edge */}
      {inputPort && (
        <div
          data-slot="node-card-port"
          className={[
            "absolute left-[-5px] top-1/2 -translate-y-1/2",
            "size-2.5 rounded-full",
            "bg-(--surface-primary) border-2 border-(--border-default)",
            "transition-[border-color,background,box-shadow] duration-150 ease-out",
            "hover:border-(--interactive-default) hover:bg-(--interactive-default)",
            "cursor-crosshair",
          ].join(" ")}
        />
      )}

      {/* Status badge — hidden per spec (stripe-as-status replaces badges) */}
      {statusBadge && (
        <div
          data-slot="node-card-status-badge"
          className="hidden"
          aria-label={statusBadge}
        />
      )}

      {/* Header: icon + name + avatar stack */}
      <div
        data-slot="node-card-header"
        className="flex items-center gap-2 px-3 pt-2.5 pb-1.5 relative z-[2]"
      >
        {icon && (
          <div
            aria-hidden="true"
            data-slot="node-card-icon"
            className={cn(
              "w-4 h-4 flex-shrink-0 flex items-center justify-center leading-none",
              iconColorClass
            )}
          >
            {icon}
          </div>
        )}

        <span
          data-slot="node-card-title"
          className={[
            "text-sm font-medium text-(--text-heading)",
            "overflow-hidden text-ellipsis whitespace-nowrap",
            "flex-1 min-w-0 tracking-tight",
          ].join(" ")}
        >
          {title}
        </span>

        {/* Soul avatar */}
        {soul && (
          <div
            data-slot="node-card-avatar-stack"
            className="flex flex-shrink-0"
          >
            <SoulAvatar soul={soul} />
          </div>
        )}
      </div>

      {/* Meta row — uppercase mono, accent-coloured */}
      {metaItems && (
        <div
          data-slot="node-card-meta"
          className={[
            "flex items-center gap-1 flex-wrap",
            "px-3",
            ports && ports.length > 0 ? "pb-0" : "pb-2.5",
            "font-mono text-2xs tracking-wider uppercase",
            "text-(--accent-9) opacity-80",
            "relative z-[2]",
          ].join(" ")}
        >
          {metaItems.map((item, idx) => (
            <React.Fragment key={idx}>
              {idx > 0 && (
                <span className="text-(--accent-7) opacity-60">&middot;</span>
              )}
              <span>{item}</span>
            </React.Fragment>
          ))}
        </div>
      )}

      {/* Body (optional children) */}
      {children && (
        <div
          data-slot="node-card-body"
          className="px-3 pb-2.5 font-mono text-3xs text-(--text-muted) leading-relaxed"
        >
          {children}
        </div>
      )}

      {/* Named port rows — conditional output port dots */}
      {ports && ports.length > 0 && (
        <div
          data-slot="node-card-port-rows"
          className="flex flex-col gap-1.5 pb-4 relative z-[2]"
        >
          {ports.map((port, idx) => (
            <div
              key={idx}
              className="flex items-center justify-end relative px-3 py-1.5"
            >
              <span className="font-mono text-2xs text-(--text-muted) tracking-wider uppercase mr-2">
                {port.name}
              </span>
              <div
                className={cn(
                  "absolute right-[-5px] top-1/2 -translate-y-1/2",
                  "size-2.5 rounded-full",
                  "transition-[box-shadow,transform] duration-150 ease-out",
                  "hover:scale-[1.3]",
                  port.type === "pass"
                    ? "bg-(--success-9) hover:shadow-[0_0_8px_color-mix(in_srgb,var(--accent-9)_40%,transparent)]"
                    : port.type === "fail"
                      ? "bg-(--danger-9)"
                      : "bg-(--border-default)"
                )}
              />
            </div>
          ))}
        </div>
      )}

      {/* Cost badge — amber-themed pill, positioned bottom-right */}
      {cost && (
        <div
          data-slot="node-card-cost"
          className={[
            "absolute bottom-[-9px] right-3",
            "px-2 py-0.5",
            "bg-(--accent-3) border border-(--accent-6)",
            "rounded-full",
            "font-mono text-3xs text-(--accent-11)",
            "tracking-wider",
            "pointer-events-none",
            "z-[3]",
          ].join(" ")}
        >
          {cost}
        </div>
      )}

      {/* Output port handle — right edge */}
      {outputPort && (
        <div
          data-slot="node-card-port"
          className={[
            "absolute right-[-5px] top-1/2 -translate-y-1/2",
            "size-2.5 rounded-full",
            "bg-(--surface-primary) border-2 border-(--border-default)",
            "transition-[border-color,background,box-shadow] duration-150 ease-out",
            "hover:border-(--interactive-default) hover:bg-(--interactive-default)",
            "cursor-crosshair",
          ].join(" ")}
        />
      )}
    </div>
  )
}
