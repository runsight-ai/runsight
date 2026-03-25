// Design system tokens:
//   Toast container — elevation-overlay-surface (surface-overlay = neutral-2) bg,
//                     elevation-border-raised (rgba(255,255,255,0.1)) border,
//                     radius-lg (6px), elevation-overlay-shadow box-shadow
//   Padding: space-3 (12px) / space-4 (16px), gap: space-3 (12px)
//   Min-width: 300px, max-width: 420px
//   slide-up animation: globals.css (duration-200 ease-out)
//   Title: font-size-md (14px), font-weight-medium (500), text-heading
//   Description: font-size-sm (13px), text-secondary, margin-top space-0-5 (2px)
//   Dismiss button: text-muted, cursor-pointer, flex-shrink-0
//   Left border accent: 3px solid per variant (inline style — kept as-is)
// ARIA: role="status" for info/success; role="alert" for danger/warning

import * as React from "react"

import { cn } from "@/utils/helpers"

type ToastVariant = "success" | "danger" | "warning" | "info"

const toastAccentColors: Record<ToastVariant, string> = {
  success: "var(--success-9)",
  danger:  "var(--danger-9)",
  warning: "var(--warning-9)",
  info:    "var(--info-9)",
}

interface ToastProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "title"> {
  variant?: ToastVariant
  title?: React.ReactNode
  description?: React.ReactNode
  onDismiss?: () => void
}

function Toast({
  className,
  variant = "info",
  title,
  description,
  onDismiss,
  children,
  ...props
}: ToastProps) {
  const isAlert = variant === "danger" || variant === "warning"

  return (
    <div
      role={isAlert ? "alert" : "status"}
      data-slot="toast"
      data-variant={variant}
      style={{ borderLeft: `3px solid ${toastAccentColors[variant]}` }}
      className={cn(
        // Layout
        "flex items-start gap-3",
        // Sizing
        "min-w-[300px] max-w-[420px]",
        // Spacing: py-3 px-4
        "p-3 px-4",
        // Surface: elevation-overlay-surface (surface-overlay = neutral-2)
        "bg-surface-overlay",
        // Border: border-width-thin (1px), elevation-border-raised
        "border border-[rgba(255,255,255,0.1)]",
        // Radius: radius-lg = 6px
        "rounded-lg",
        // Shadow: elevation-overlay-shadow
        "shadow-overlay",
        // Pointer events
        "pointer-events-auto",
        // Entrance animation: slide-up duration-200 ease-out
        "[animation:slide-up_var(--duration-200)_var(--ease-out)]",
        className
      )}
      {...props}
    >
      <div
        data-slot="toast-content"
        className="flex-1 min-w-0"
      >
        {title && (
          <p
            data-slot="toast-title"
            className="text-md font-medium text-heading"
          >
            {title}
          </p>
        )}
        {description && (
          <p
            data-slot="toast-description"
            className="text-sm text-secondary mt-0.5"
          >
            {description}
          </p>
        )}
        {children}
      </div>
      {onDismiss && (
        <button
          type="button"
          data-slot="toast-dismiss"
          aria-label="Dismiss"
          onClick={onDismiss}
          className="shrink-0 text-muted cursor-pointer"
        >
          <svg
            aria-hidden="true"
            width="14"
            height="14"
            viewBox="0 0 14 14"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M1 1L13 13M13 1L1 13"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        </button>
      )}
    </div>
  )
}

export { Toast }
export type { ToastVariant, ToastProps }
