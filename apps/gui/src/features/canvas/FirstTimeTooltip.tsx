import { useState, useEffect, useCallback } from "react";

const STORAGE_KEY = "runsight:firstTimeTooltipDismissed";
const AUTO_DISMISS_MS = 8000;

export function FirstTimeTooltip() {
  const [visible, setVisible] = useState(() => {
    return localStorage.getItem(STORAGE_KEY) !== "true";
  });

  const dismiss = useCallback(() => {
    setVisible(false);
    localStorage.setItem(STORAGE_KEY, "true");
  }, []);

  useEffect(() => {
    if (!visible) return;

    const timer = setTimeout(dismiss, AUTO_DISMISS_MS);

    const handleClick = () => dismiss();
    const handleKeydown = () => dismiss();

    window.addEventListener("click", handleClick);
    window.addEventListener("keydown", handleKeydown);

    return () => {
      clearTimeout(timer);
      window.removeEventListener("click", handleClick);
      window.removeEventListener("keydown", handleKeydown);
    };
  }, [visible, dismiss]);

  if (!visible) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="absolute bottom-6 left-1/2 -translate-x-1/2 z-50 rounded-lg bg-surface-overlay px-4 py-3 text-sm text-secondary shadow-lg border border-border animate-in fade-in slide-in-from-bottom-2 duration-300"
    >
      Click anywhere or press any key to start editing your workflow.
    </div>
  );
}
