// Design system tokens: neutral-2 (background), font-mono (font family),
// font-size-sm (font size), syntax-key (keyword color), syntax-string (string color),
// syntax-value (value color), border-subtle (border), radius-md (border radius)

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
        "group/code-block relative overflow-hidden rounded-radius-md border border-border-subtle bg-neutral-2",
        numbered && "code-block--numbered",
        className
      )}
      {...props}
    >
      {/* Header bar */}
      {(language || showCopy) && (
        <div className="flex items-center justify-between border-b border-border-subtle px-3 py-1.5">
          {language && (
            <span className="text-font-size-xs text-secondary uppercase tracking-wider font-mono">
              {language}
            </span>
          )}
          {showCopy && (
            <button
              type="button"
              onClick={handleCopy}
              aria-label="Copy code"
              className={cn(
                "code-block__copy ml-auto inline-flex items-center gap-1 rounded-radius-xs px-2 py-0.5 text-font-size-xs transition-colors",
                "text-secondary hover:text-primary hover:bg-surface-hover",
                copied && "text-success-11"
              )}
            >
              {copied ? "Copied!" : "copy"}
            </button>
          )}
        </div>
      )}

      {/* Code area — neutral-2 bg, font-mono, font-size-sm */}
      <pre
        data-slot="code-block-content"
        className="overflow-x-auto bg-neutral-2 p-space-4 font-mono text-font-size-sm leading-relaxed text-primary"
      >
        <code>{children}</code>
      </pre>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Syntax highlight helper components
// These use the design-system syntax token colors:
//   --syntax-key, --syntax-string, --syntax-value
// ---------------------------------------------------------------------------

export function SyntaxKey({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={cn("token-key text-[color:var(--syntax-key)]", className)}>
      {children}
    </span>
  )
}

export function SyntaxString({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={cn("token-string text-[color:var(--syntax-string)]", className)}>
      {children}
    </span>
  )
}

export function SyntaxValue({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={cn("token-value text-[color:var(--syntax-value)]", className)}>
      {children}
    </span>
  )
}
