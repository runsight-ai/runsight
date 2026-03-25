import * as React from "react"
import { useState } from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/utils/helpers"

const codeBlockVariants = cva(
  // base — surface-primary, border, left accent, radius, padding, mono font, relative
  [
    "bg-surface-primary",
    "border border-border-subtle border-l-[4px] border-l-interactive-default",
    "rounded-md",
    "p-4 overflow-x-auto",
    "font-mono text-sm leading-relaxed text-primary",
    "[tab-size:2]",
    "relative",
    "group", // enables group-hover for copy button
    // scrollbar
    "[&::-webkit-scrollbar]:h-1.5",
    "[&::-webkit-scrollbar-thumb]:bg-neutral-7 [&::-webkit-scrollbar-thumb]:rounded-full",
  ],
  {
    variants: {
      numbered: {
        true: "[counter-reset:line]",
        false: null,
      },
    },
    defaultVariants: {
      numbered: false,
    },
  }
)

export interface CodeBlockProps
  extends React.ComponentProps<"div">,
    VariantProps<typeof codeBlockVariants> {
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
      className={cn(codeBlockVariants({ numbered }), className)}
      {...props}
    >
      {/* Header bar — language label + copy button */}
      {(language || showCopy) && (
        <div className="flex items-center justify-between mb-2">
          {language && (
            <span className="text-2xs font-medium tracking-wider uppercase text-muted">
              {language}
            </span>
          )}
          {showCopy && (
            <button
              type="button"
              onClick={handleCopy}
              aria-label="Copy"
              className={cn(
                // ghost xs icon button — inline Tailwind translation
                "absolute top-2 right-2",
                "inline-flex items-center justify-center",
                "h-6 w-6 p-0 rounded-sm",
                "bg-transparent border border-transparent",
                "text-secondary text-2xs cursor-pointer",
                "opacity-0 transition-opacity duration-100",
                "group-hover:opacity-100",
                "hover:bg-surface-hover hover:text-primary",
                "active:bg-surface-active",
                copied && "text-success-11"
              )}
            >
              {copied ? "✓" : "⧉"}
            </button>
          )}
        </div>
      )}

      {/* Code area */}
      <pre
        data-slot="code-block-content"
        className="overflow-x-auto"
      >
        <code>
          {numbered && typeof children === "string"
            ? children.split("\n").map((line, i) => (
                <span
                  key={i}
                  className="[counter-increment:line] block before:content-[counter(line)] before:inline-block before:w-[2.5em] before:mr-3 before:text-right before:text-muted before:select-none"
                >
                  {line}
                </span>
              ))
            : children}
        </code>
      </pre>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Syntax highlight helper components
// These use design-system syntax token colors via arbitrary CSS var values.
// Token colors are defined on .code-block in components.css — but since we
// are no longer wrapping in .code-block, we apply the CSS vars directly.
// ---------------------------------------------------------------------------

export function SyntaxKey({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={cn("text-[var(--syntax-key)]", className)}>
      {children}
    </span>
  )
}

export function SyntaxString({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={cn("text-[var(--syntax-string)]", className)}>
      {children}
    </span>
  )
}

export function SyntaxValue({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={cn("text-[var(--syntax-value)]", className)}>
      {children}
    </span>
  )
}

export function SyntaxComment({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={cn("text-[var(--syntax-comment)]", className)}>
      {children}
    </span>
  )
}

export function SyntaxPunct({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={cn("text-[var(--syntax-punct)]", className)}>
      {children}
    </span>
  )
}
