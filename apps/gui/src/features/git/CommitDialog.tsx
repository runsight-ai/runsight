import { useState } from "react";
import { useCommit } from "@/queries/git";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogBody,
  DialogFooter,
} from "@runsight/ui/dialog";
import { Button } from "@runsight/ui/button";
import { DiffView } from "./DiffView";

interface FileStatus {
  path: string;
  status: string;
}

interface CommitDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  files: FileStatus[];
  onCommitSuccess?: () => void;
}

export function CommitDialog({ open, onOpenChange, files, onCommitSuccess }: CommitDialogProps) {
  const [message, setMessage] = useState("");
  const commit = useCommit();

  function handleSubmit() {
    if (!message.trim()) return;
    commit.mutate(message.trim(), {
      onSuccess: () => {
        setMessage("");
        onOpenChange(false);
        onCommitSuccess?.();
      },
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="lg">
        <DialogHeader>
          <DialogTitle>Commit Changes</DialogTitle>
        </DialogHeader>
        <DialogBody className="space-y-4">
          {/* File list */}
          <div>
            <h4 className="text-xs font-medium text-secondary uppercase tracking-wide mb-2">
              Changed files ({files.length})
            </h4>
            <ul className="space-y-1">
              {files.map((file) => (
                <li
                  key={file.path}
                  className="flex items-center gap-2 text-sm font-mono"
                >
                  <span className="text-xs text-secondary uppercase w-16 shrink-0">
                    {file.status}
                  </span>
                  <span className="text-heading truncate">{file.path}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Diff preview */}
          <DiffView />

          {/* Commit message */}
          <div>
            <label
              htmlFor="commit-message"
              className="block text-xs font-medium text-secondary uppercase tracking-wide mb-2"
            >
              Commit message
            </label>
            <textarea
              id="commit-message"
              className="w-full rounded-md border border-border-default bg-transparent px-3 py-2 text-sm text-heading placeholder:text-muted focus:outline-none focus:ring-1 focus:ring-interactive-default resize-none"
              rows={3}
              placeholder="Describe your changes..."
              value={message}
              onChange={(e) => setMessage(e.target.value)}
            />
          </div>
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={handleSubmit}
            disabled={!message.trim() || commit.isPending}
          >
            {commit.isPending ? "Committing..." : "Commit"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
