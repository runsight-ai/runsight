import { useState } from "react";
import { Info, AlertTriangle, X } from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface BannerCondition {
  type: "explore" | "uncommitted" | "regressions";
  active: boolean;
  message?: string;
  action?: { label: string; onClick: () => void };
}

export interface PriorityBannerProps {
  conditions: BannerCondition[];
}

// ---------------------------------------------------------------------------
// Priority & styling
// ---------------------------------------------------------------------------

/** Banner priority order — earlier index = higher priority. */
const BANNER_PRIORITY: BannerCondition["type"][] = [
  "explore",
  "uncommitted",
  "regressions",
];

const EXPLORE_DISMISS_KEY = "runsight:explore-banner-dismissed";

/** Style mapping: explore -> info tokens, uncommitted/regressions -> warning tokens. */
const STYLE_MAP: Record<
  BannerCondition["type"],
  { bg: string; border: string; text: string }
> = {
  explore: {
    bg: "bg-info-3",
    border: "border-info-7",
    text: "text-info-11",
  },
  uncommitted: {
    bg: "bg-warning-3",
    border: "border-warning-7",
    text: "text-warning-11",
  },
  regressions: {
    bg: "bg-warning-3",
    border: "border-warning-7",
    text: "text-warning-11",
  },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function PriorityBanner({ conditions }: PriorityBannerProps) {
  // Persistent dismiss for explore (localStorage)
  const [exploreDismissed, setExploreDismissed] = useState(
    () => localStorage.getItem(EXPLORE_DISMISS_KEY) === "true",
  );

  // Session-scoped dismiss tracking via Set
  const [dismissedSet, setDismissedSet] = useState<Set<string>>(() => new Set());

  // Build effective dismissed set including explore persistence
  const isDismissed = (type: string) => {
    if (type === "explore" && exploreDismissed) return true;
    return dismissedSet.has(type);
  };

  // Find highest-priority active + non-dismissed condition
  const winner = BANNER_PRIORITY.map((type) =>
    conditions.find((c) => c.type === type && c.active),
  ).find((c) => c != null);

  // If no active condition, or the winner is dismissed, render nothing.
  // Sticky dismiss: if the top-priority banner was dismissed, do NOT
  // fall through to the next one.
  if (!winner || isDismissed(winner.type)) return null;

  const handleDismiss = () => {
    if (winner.type === "explore") {
      setExploreDismissed(true);
      localStorage.setItem(EXPLORE_DISMISS_KEY, "true");
    } else {
      setDismissedSet((prev) => new Set(prev).add(winner.type));
    }
  };

  const style = STYLE_MAP[winner.type];
  const Icon = winner.type === "explore" ? Info : AlertTriangle;

  return (
    <div
      className={`flex items-center gap-2 mx-3 mt-2 mb-2 px-3 py-2 text-sm rounded-md ${style.bg} border ${style.border} ${style.text}`}
      role="status"
    >
      <Icon className="size-4 shrink-0" />
      {winner.message && <span>{winner.message}</span>}
      {winner.action && (
        <button
          type="button"
          className={`font-medium underline underline-offset-2 ${style.text} hover:text-heading bg-transparent border-none cursor-pointer`}
          onClick={winner.action.onClick}
        >
          {winner.action.label}
        </button>
      )}
      <button
        type="button"
        aria-label="Dismiss banner"
        className="ml-auto p-1 text-muted hover:text-primary bg-transparent border-none cursor-pointer text-base"
        onClick={handleDismiss}
      >
        <X className="size-3.5" />
      </button>
    </div>
  );
}
