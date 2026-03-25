/**
 * Workflow icon utilities.
 *
 * These return JSX so the file keeps the .tsx extension.
 */

import type { ReactNode } from "react";

export function getWorkflowIcon(name: string): ReactNode {
  const iconClass = "w-5 h-5";
  const lower = name.toLowerCase();
  if (lower.includes("code") || lower.includes("review")) {
    return (
      <svg className={iconClass} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <rect x="2" y="3" width="20" height="6" rx="2"/>
        <rect x="2" y="15" width="20" height="6" rx="2"/>
      </svg>
    );
  }
  if (lower.includes("moderation") || lower.includes("content")) {
    return (
      <svg className={iconClass} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M12 2L2 7l10 5 10-5-10-5z"/>
        <path d="M2 17l10 5 10-5"/>
        <path d="M2 12l10 5 10-5"/>
      </svg>
    );
  }
  if (lower.includes("report") || lower.includes("daily")) {
    return (
      <svg className={iconClass} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="12" cy="12" r="10"/>
        <path d="M8 12l3 3 5-5"/>
      </svg>
    );
  }
  if (lower.includes("email") || lower.includes("classifier")) {
    return (
      <svg className={iconClass} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <rect x="3" y="4" width="18" height="18" rx="2"/>
        <line x1="16" y1="2" x2="16" y2="6"/>
        <line x1="8" y1="2" x2="8" y2="6"/>
        <line x1="3" y1="10" x2="21" y2="10"/>
      </svg>
    );
  }
  if (lower.includes("support") || lower.includes("ticket")) {
    return (
      <svg className={iconClass} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z"/>
      </svg>
    );
  }
  if (lower.includes("sync") || lower.includes("data")) {
    return (
      <svg className={iconClass} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="12" cy="12" r="10"/>
        <line x1="15" y1="9" x2="9" y2="15"/>
        <line x1="9" y1="9" x2="15" y2="15"/>
      </svg>
    );
  }
  return (
    <svg className={iconClass} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="3" y="3" width="7" height="7"/>
      <rect x="14" y="3" width="7" height="7"/>
      <rect x="14" y="14" width="7" height="7"/>
      <rect x="3" y="14" width="7" height="7"/>
    </svg>
  );
}

export function getWorkflowIconBg(name: string): string {
  const lower = name.toLowerCase();
  if (lower.includes("code") || lower.includes("review")) return "bg-[var(--accent-3)] text-[var(--interactive-default)]";
  if (lower.includes("moderation") || lower.includes("content")) return "bg-[var(--warning-12)] text-[var(--warning-9)]";
  if (lower.includes("report") || lower.includes("daily")) return "bg-[var(--success-12)] text-[var(--success-9)]";
  if (lower.includes("email") || lower.includes("classifier")) return "bg-[var(--accent-3)] text-[var(--interactive-default)]";
  if (lower.includes("support") || lower.includes("ticket")) return "bg-[var(--surface-raised)] text-[var(--muted-foreground)]";
  if (lower.includes("sync") || lower.includes("data")) return "bg-[var(--error-12)] text-[var(--danger-9)]";
  return "bg-[var(--accent-3)] text-[var(--interactive-default)]";
}
