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
      className="flex items-center gap-2 px-4 py-2 bg-warning-3 border-b border-warning-7 text-sm"
      role="status"
    >
      <AlertTriangle className="h-4 w-4 shrink-0 text-[var(--warning-9)]" />
      <span className="text-[var(--warning-11)]">
        {fileCount} uncommitted {fileCount === 1 ? "change" : "changes"}
      </span>
      <Link
        to="/settings"
        className="ml-1 font-medium underline underline-offset-2 text-[var(--warning-11)] hover:text-[var(--warning-12)]"
      >
        Commit
      </Link>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        className="ml-auto p-0.5 rounded hover:bg-[var(--warning-5)] text-[var(--warning-9)]"
        aria-label="Dismiss uncommitted changes banner"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
