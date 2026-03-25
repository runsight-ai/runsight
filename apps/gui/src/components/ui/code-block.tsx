// BEM classes: .code-block, .code-block__copy, .code-block--numbered
// .code-block__header, .code-block__lang, .code-inline
// Tokens: neutral-2 (background via surface-primary), font-mono, font-size-sm
// border-subtle, border-left accent (interactive-default), radius-md, space-4
// Syntax tokens: syntax-key, syntax-string, syntax-value, syntax-comment, syntax-punct

import * as React from "react"
import { useState } from "react"

import { cn } from "@/utils/helpers"

export interface CodeBlockProps extends React.ComponentProps<"div"> {
  /** Code content to display */
  children: React.ReactNode
  /** Optional language label shown in header */
  language?: string
  /** Whether to show line numbers */
  numbered?: boolean
  /** Whether to show copy button (default: true) */
  showCopy?: boolean
}

export function CodeBlock({
  children,
  language,
  numbered = false,
  showCopy = true,
  className,
  ...props
}: CodeBlockProps) {
  const [copied, setCopied] = useState(false)

  function handleCopy() {
    const text =
      typeof children === "string"
        ? children
        : (document.querySelector("[data-slot='code-block-content']")?.textContent ?? "")
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div
      data-slot="code-block"
      data-numbered={numbered ? true : undefined}
      className={cn(
        "code-block",
        numbered && "code-block--numbered",
        className
      )}
      {...props}
    >
      {/* Header bar */}
      {(language || showCopy) && (
        <div className="code-block__header flex items-center justify-between border-b border-border-subtle px-3 py-1.5">
          {language && (
            <span className="code-block__lang">
              {language}
            </span>
          )}
          {showCopy && (
            <button
              type="button"
              onClick={handleCopy}
              aria-label="Copy code"
              className={cn(
                "btn btn--ghost btn--icon code-block__copy ml-auto",
                copied && "text-success-11"
              )}
            >
              {copied ? "✓" : "⧉"}
            </button>
          )}
        </div>
      )}

      {/* Code area — font-mono, font-size-sm */}
      <pre
        data-slot="code-block-content"
        className="overflow-x-auto p-4"
      >
        <code>{children}</code>
      </pre>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Syntax highlight helper components
// These use the design-system syntax token colors:
//   syntax-key (.token-key), syntax-string (.token-string), syntax-value (.token-value)
// ---------------------------------------------------------------------------

export function SyntaxKey({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={cn("token-key", className)}>
      {children}
    </span>
  )
}

export function SyntaxString({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={cn("token-string", className)}>
      {children}
    </span>
  )
}

export function SyntaxValue({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={cn("token-value", className)}>
      {children}
    </span>
  )
}

export function SyntaxComment({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={cn("token-comment", className)}>
      {children}
    </span>
  )
}

export function SyntaxPunct({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={cn("token-punct", className)}>
      {children}
    </span>
  )
}
