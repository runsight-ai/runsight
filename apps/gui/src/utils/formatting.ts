/**
 * Shared formatting utilities.
 *
 * Pure functions — no JSX, no side-effects.
 */

// ── Duration ────────────────────────────────────────────────────────────────

export function formatDuration(seconds: number | null | undefined): string {
  if (!seconds || seconds <= 0) return "\u2014";

  const totalSeconds = Math.max(1, Math.round(seconds));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;

  if (hours > 0) {
    return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
  }
  if (minutes > 0) {
    return secs > 0 ? `${minutes}m ${String(secs).padStart(2, "0")}s` : `${minutes}m`;
  }
  return `${secs}s`;
}

// ── Text ────────────────────────────────────────────────────────────────────

export function truncateText(
  text: string | null | undefined,
  maxLength: number,
): string {
  if (!text) return "\u2014";
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + "...";
}

// ── Timestamps ──────────────────────────────────────────────────────────────

export function formatTimestamp(
  timestamp: number | null | undefined,
): string {
  if (!timestamp) return "\u2014";
  const date = new Date(timestamp * 1000);
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  });
}

// ── Cost ────────────────────────────────────────────────────────────────────

export function formatCost(cost: number | null | undefined): string {
  if (cost === null || cost === undefined) return "\u2014";
  if (cost === 0) return "$0.000";
  if (cost < 0.001) return `$${cost.toFixed(6)}`;
  return `$${cost.toFixed(3)}`;
}

// ── Relative time ───────────────────────────────────────────────────────────

export function getTimeAgo(date: string | undefined): string {
  if (!date) return "\u2014";
  const now = new Date();
  const then = new Date(date);
  const diffMs = now.getTime() - then.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);
  const diffWeeks = Math.floor(diffDays / 7);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins} min ago`;
  if (diffHours < 24)
    return `${diffHours} hour${diffHours > 1 ? "s" : ""} ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? "s" : ""} ago`;
  if (diffWeeks < 4)
    return `${diffWeeks} week${diffWeeks > 1 ? "s" : ""} ago`;
  return then.toLocaleDateString();
}
