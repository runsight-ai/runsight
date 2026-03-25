import { Tooltip as TooltipPrimitive } from "@base-ui/react/tooltip"

import { cn } from "@/utils/helpers"

// BEM classes: .tooltip-content, .tooltip-content--top, .tooltip-content--bottom
// Tokens: surface-raised, text-primary, font-size-xs, z-popover, neutral-3, neutral-5
// Soul-tip BEM: .soul-tip-wrap, .soul-tip, .soul-tip__name, .soul-tip__dot,
//               .soul-tip__row, .soul-tip__key, .soul-tip__val, .soul-tip__prompt

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
          className={cn(
            "tooltip-content",
            side === "top" && "tooltip-content--top",
            side === "bottom" && "tooltip-content--bottom",
            "data-[state=delayed-open]:animate-in data-[state=delayed-open]:fade-in-0 data-[state=delayed-open]:zoom-in-95",
            "data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95",
            "data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95",
            className
          )}
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
// Renders .soul-tip-wrap > .node-card__avatar + .soul-tip (BEM from patterns.css)
// Usage: wrap around a .node-card__avatar element inside a .node-card__avatar-stack
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
    <span className="soul-tip-wrap">
      {/* Avatar circle */}
      <span
        className="node-card__avatar"
        style={{ background: color }}
      >
        {initial}
      </span>

      {/* Tooltip panel — visible on .soul-tip-wrap:hover via CSS */}
      <span className="soul-tip">
        <span className="soul-tip__name">
          <span className="soul-tip__dot" style={{ background: color }} />
          {name}
        </span>
        {allRows.map(({ key, val }) => (
          <span key={key} className="soul-tip__row">
            <span className="soul-tip__key">{key}</span>
            <span className="soul-tip__val">{val}</span>
          </span>
        ))}
        {prompt && (
          <span className="soul-tip__prompt">{prompt}</span>
        )}
      </span>
    </span>
  )
}

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider, SoulTip }
