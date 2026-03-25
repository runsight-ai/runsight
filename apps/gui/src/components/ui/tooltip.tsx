import { Tooltip as TooltipPrimitive } from "@base-ui/react/tooltip"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/utils/helpers"

// ---------------------------------------------------------------------------
// Variants
// ---------------------------------------------------------------------------

const tooltipContentVariants = cva(
  [
    // base — matches .tooltip-content spec
    "px-2 py-1",
    "bg-(--neutral-3)",
    "text-(--text-primary)",
    "text-[length:var(--font-size-xs)]",
    "border border-(--neutral-5)",
    "rounded-[var(--radius-sm)]",
    "whitespace-nowrap max-w-[240px]",
    "pointer-events-none",
    "shadow-[0_4px_12px_rgba(0,0,0,0.3)]",
    // open/close animations
    "data-[state=delayed-open]:animate-in data-[state=delayed-open]:fade-in-0 data-[state=delayed-open]:zoom-in-95",
    "data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95",
    "data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95",
  ].join(" ")
)

// ---------------------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------------------

function TooltipProvider({
  delay = 0,
  ...props
}: TooltipPrimitive.Provider.Props) {
  return (
    <TooltipPrimitive.Provider
      data-slot="tooltip-provider"
      delay={delay}
      {...props}
    />
  )
}

function Tooltip({ ...props }: TooltipPrimitive.Root.Props) {
  return <TooltipPrimitive.Root data-slot="tooltip" {...props} />
}

function TooltipTrigger({ ...props }: TooltipPrimitive.Trigger.Props) {
  return <TooltipPrimitive.Trigger data-slot="tooltip-trigger" {...props} />
}

function TooltipContent({
  className,
  side = "top",
  sideOffset = 4,
  align = "center",
  alignOffset = 0,
  children,
  ...props
}: TooltipPrimitive.Popup.Props &
  Pick<
    TooltipPrimitive.Positioner.Props,
    "align" | "alignOffset" | "side" | "sideOffset"
  >) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Positioner
        align={align}
        alignOffset={alignOffset}
        side={side}
        sideOffset={sideOffset}
        className="isolate z-50"
      >
        <TooltipPrimitive.Popup
          data-slot="tooltip-content"
          className={cn(tooltipContentVariants(), className)}
          {...props}
        >
          {children}
          <TooltipPrimitive.Arrow className="z-50 size-2.5 translate-y-[calc(-50%-2px)] rotate-45 rounded-[2px] bg-surface-raised fill-surface-raised data-[side=bottom]:top-1 data-[side=inline-end]:top-1/2! data-[side=inline-end]:-left-1 data-[side=inline-end]:-translate-y-1/2 data-[side=inline-start]:top-1/2! data-[side=inline-start]:-right-1 data-[side=inline-start]:-translate-y-1/2 data-[side=left]:top-1/2! data-[side=left]:-right-1 data-[side=left]:-translate-y-1/2 data-[side=right]:top-1/2! data-[side=right]:-left-1 data-[side=right]:-translate-y-1/2 data-[side=top]:-bottom-2.5" />
        </TooltipPrimitive.Popup>
      </TooltipPrimitive.Positioner>
    </TooltipPrimitive.Portal>
  )
}

// ---------------------------------------------------------------------------
// SoulTip — rich avatar tooltip showing soul/model details
// Pure Tailwind — no BEM classes
// ---------------------------------------------------------------------------

export interface SoulTipProps {
  /** Single uppercase letter shown in the avatar circle */
  initial: string
  /** HSL or hex background colour for the avatar and dot */
  color: string
  /** Soul name (e.g. "writer_main") */
  name: string
  /** Model identifier (e.g. "gpt-4o") */
  model?: string
  /** Provider name (e.g. "OpenAI") */
  provider?: string
  /** Optional prompt preview text (clamped to 2 lines) */
  prompt?: string
  /** Additional key/value rows to show in the tooltip */
  rows?: Array<{ key: string; val: string }>
}

function SoulTip({
  initial,
  color,
  name,
  model,
  provider,
  prompt,
  rows = [],
}: SoulTipProps) {
  const allRows = [
    ...(model ? [{ key: "Model", val: model }] : []),
    ...(provider ? [{ key: "Provider", val: provider }] : []),
    ...rows,
  ]

  return (
    <span className="relative inline-flex group/soul-tip">
      {/* Avatar circle */}
      <span
        className={[
          "inline-flex items-center justify-center",
          "size-5 rounded-full", // icon-size-lg = 20px
          "text-3xs font-semibold text-white",
          "border border-[color-mix(in_srgb,var(--neutral-6)_50%,transparent)]",
          "cursor-default select-none",
        ].join(" ")}
        style={{ background: color }}
      >
        {initial}
      </span>

      {/* Tooltip panel — visible on group hover */}
      <span
        className={[
          // position — float above avatar
          "absolute bottom-[calc(100%+10px)] left-1/2 -translate-x-1/2",
          // sizing
          "w-[200px]", // soul-tip spec: 200px
          // surface
          "bg-(--neutral-2) border border-(--neutral-4)",
          "rounded-[var(--radius-md)]",
          "px-3 py-2",
          "shadow-[0_8px_24px_rgba(0,0,0,0.4)]",
          // typography base
          "font-mono text-3xs",
          // visibility — opacity transition, shown on group hover
          "opacity-0 pointer-events-none",
          "transition-opacity duration-[var(--duration-100)]",
          "group-hover/soul-tip:opacity-100",
          // z
          "z-[var(--z-popover)]",
        ].join(" ")}
      >
        {/* Caret arrow pointing down */}
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
            className="size-1.5 rounded-full flex-shrink-0"
            style={{ background: color }}
          />
          <span className="text-3xs text-(--text-primary) font-medium">{name}</span>
        </span>

        {/* Key/value rows */}
        {allRows.map(({ key, val }) => (
          <span key={key} className="flex justify-between items-baseline mb-[3px]">
            <span className="text-(--text-muted) uppercase tracking-wider text-3xs">{key}</span>
            <span className="text-(--accent-11) font-mono text-3xs">{val}</span>
          </span>
        ))}

        {/* Prompt preview */}
        {prompt && (
          <span className="block text-3xs text-(--text-muted) mt-1.5 leading-tight line-clamp-2">
            {prompt}
          </span>
        )}
      </span>
    </span>
  )
}

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider, SoulTip }
