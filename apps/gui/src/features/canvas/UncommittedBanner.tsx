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
      className="absolute left-3 right-3 flex items-center gap-2 px-3 py-2 bg-warning-3 border border-warning-7 rounded-md text-sm text-warning-11 z-[11]"
      style={{ top: "calc(var(--space-3) + 44px + var(--space-2))" }}
      role="status"
    >
      <AlertTriangle className="h-4 w-4 shrink-0 text-warning-9" />
      <span className="text-warning-11">
        {fileCount} uncommitted {fileCount === 1 ? "change" : "changes"}
      </span>
      <Link
        to="/settings"
        className="ml-1 font-medium underline underline-offset-2 text-warning-11 hover:text-heading"
      >
        Commit
      </Link>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        className="ml-auto p-1 bg-transparent border-none text-muted cursor-pointer hover:text-primary text-base"
        aria-label="Dismiss uncommitted changes banner"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
