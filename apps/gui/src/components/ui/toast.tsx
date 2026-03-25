// Design system tokens used by BEM classes in components.css:
//   .toast        — background: var(--elevation-overlay-surface); (surface-raised equivalent)
//                   border: var(--elevation-border-raised); border-radius: var(--radius-lg)
//                   box-shadow: var(--elevation-overlay-shadow)
//   .toast--success / .toast--danger / .toast--warning / .toast--info
//                 — variant modifier classes for semantic color variants
//   .toast__icon  — flex-shrink: 0; color set per variant
//   .toast__content — flex: 1
//   .toast__title  — font-weight: medium; color: var(--text-heading)
//   .toast__description — color: var(--text-secondary)
//   .toast__dismiss — color: var(--text-muted)
// ARIA: role="status" for info/success; role="alert" for danger/warning

import * as React from "react"

import { cn } from "@/utils/helpers"

type ToastVariant = "success" | "danger" | "warning" | "info"

const toastAccentColors: Record<ToastVariant, string> = {
  success: "var(--success-9)",
  danger: "var(--danger-9)",
  warning: "var(--warning-9)",
  info: "var(--info-9)",
}

interface ToastProps extends React.HTMLAttributes<HTMLDivElement> {
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
      style={{
        borderLeft: `3px solid ${toastAccentColors[variant]}`,
      }}
      className={cn("toast", `toast--${variant}`, className)}
      {...props}
    >
      <div className="toast__content">
        {title && (
          <p data-slot="toast-title" className="toast__title">
            {title}
          </p>
        )}
        {description && (
          <p data-slot="toast-description" className="toast__description">
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
          className="toast__dismiss"
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
