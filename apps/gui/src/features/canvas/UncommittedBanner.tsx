import { useState } from "react";
import { Link } from "react-router";
import { AlertTriangle, X } from "lucide-react";
import { useGitStatus } from "@/queries/git";

export function UncommittedBanner() {
  const [dismissed, setDismissed] = useState(false);
  const { data: gitStatus } = useGitStatus();

  if (dismissed || !gitStatus || gitStatus.is_clean) {
    return null;
  }

  const fileCount = gitStatus.uncommitted_files.length;

  return (
    <div
      className="absolute left-[var(--space-3)] right-[var(--space-3)] flex items-center gap-[var(--space-2)] px-[var(--space-3)] py-[var(--space-2)] bg-[var(--warning-3)] border border-[var(--warning-7)] rounded-[var(--radius-md)] text-[var(--font-size-sm)] text-[var(--warning-11)] z-[11]"
      style={{ top: "calc(var(--space-3) + 44px + var(--space-2))" }}
      role="status"
    >
      <AlertTriangle className="h-4 w-4 shrink-0 text-[var(--warning-9)]" />
      <span className="text-[var(--warning-11)]">
        {fileCount} uncommitted {fileCount === 1 ? "change" : "changes"}
      </span>
      <Link
        to="/settings"
        className="ml-1 font-medium underline underline-offset-2 text-[var(--warning-11)] hover:text-[var(--text-heading)]"
      >
        Commit
      </Link>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        className="ml-auto p-[var(--space-1)] bg-transparent border-none text-[var(--text-muted)] cursor-pointer hover:text-[var(--text-primary)] text-base"
        aria-label="Dismiss uncommitted changes banner"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
