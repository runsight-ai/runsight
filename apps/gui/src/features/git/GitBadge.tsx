import { useState } from "react";
import { useGitStatus } from "@/queries/git";
import { Badge, BadgeDot } from "@runsight/ui/badge";
import { CommitDialog } from "./CommitDialog";

export function GitBadge() {
  const [open, setOpen] = useState(false);
  const { data: gitStatus } = useGitStatus();

  if (!gitStatus || gitStatus.is_clean) {
    return null;
  }

  const fileCount = gitStatus.uncommitted_files.length;

  return (
    <>
      <Badge
        variant="warning"
        className="cursor-pointer select-none"
        onClick={() => setOpen(true)}
        role="button"
        aria-label={`${fileCount} uncommitted ${fileCount === 1 ? "change" : "changes"}`}
      >
        <BadgeDot />
        {fileCount} uncommitted
      </Badge>
      <CommitDialog
        open={open}
        onOpenChange={setOpen}
        files={gitStatus.uncommitted_files}
      />
    </>
  );
}
