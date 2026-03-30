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
      className="flex items-center gap-2 mx-3 mt-3 px-3 py-2 text-sm bg-info-3 border border-info-7 rounded-md text-info-11"
      role="status"
    >
      <Info className="size-4 shrink-0" />
      <span>
        You are in explore mode.{" "}
        <button
          type="button"
          className="underline underline-offset-2 font-medium text-info-11 hover:text-heading"
          onClick={onAddApiKey}
        >
          Add an API key
        </button>{" "}
        to start running workflows.
      </span>
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
