import { useState } from "react";
import { Info, X } from "lucide-react";
import { useProviders } from "@/queries/settings";

const STORAGE_KEY = "runsight:explore-banner-dismissed";

export function ExploreBanner({ onAddApiKey }: { onAddApiKey?: () => void }) {
  const { data: providers } = useProviders();
  const items = providers?.items ?? [];
  const [dismissed, setDismissed] = useState(
    () => localStorage.getItem(STORAGE_KEY) === "true",
  );

  if (dismissed) return null;
  if (items.length > 0) return null;

  function handleDismiss() {
    setDismissed(true);
    localStorage.setItem(STORAGE_KEY, "true");
  }

  return (
    <div
      className="absolute top-[var(--space-3)] left-[var(--space-3)] right-[var(--space-3)] flex items-center gap-[var(--space-2)] px-[var(--space-3)] py-[var(--space-2)] text-[var(--font-size-sm)] bg-[var(--info-3)] border border-[var(--info-7)] rounded-[var(--radius-md)] text-[var(--info-11)] z-10"
      role="status"
    >
      <Info className="size-4 shrink-0" />
      <span>
        You are in explore mode.{" "}
        <button
          type="button"
          className="underline underline-offset-2 font-medium text-[var(--info-11)] hover:text-[var(--text-heading)]"
          onClick={onAddApiKey}
        >
          Add an API key
        </button>{" "}
        to start running workflows.
      </span>
      <button
        type="button"
        aria-label="Dismiss banner"
        className="ml-auto p-[var(--space-1)] text-[var(--text-muted)] hover:text-[var(--text-primary)] bg-transparent border-none cursor-pointer text-base"
        onClick={handleDismiss}
      >
        <X className="size-3.5" />
      </button>
    </div>
  );
}
