import { useState } from "react";
import { useCommitWorkflow } from "@/queries/git";
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
  workflowId?: string;
  draft?: {
    name?: string;
    description?: string;
    yaml?: string;
    canvas_state?: Record<string, unknown>;
  };
  onCommitSuccess?: () => void;
  onCommitError?: (error: Error) => void;
}

export function CommitDialog({
  open,
  onOpenChange,
  files,
  workflowId,
  draft,
  onCommitSuccess,
  onCommitError,
}: CommitDialogProps) {
  const [message, setMessage] = useState("");
  const [submitError, setSubmitError] = useState<string | null>(null);
  const commitWorkflow = useCommitWorkflow();

  function handleSubmit() {
    if (!workflowId || !message.trim()) return;
    setSubmitError(null);
    commitWorkflow.mutate(
      {
        workflowId,
        payload: {
          ...draft,
          message: message.trim(),
        },
      },
      {
        onSuccess: () => {
          setMessage("");
          setSubmitError(null);
          onOpenChange(false);
          onCommitSuccess?.();
        },
        onError: (error: Error) => {
          setSubmitError(error.message);
          onCommitError?.(error);
        },
      },
    );
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      setSubmitError(null);
    }

    onOpenChange(nextOpen);
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
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
          <DiffView draft={draft} />

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

          {submitError ? (
            <div
              role="alert"
              className="rounded-md border border-danger-7 bg-danger-3 px-3 py-2 text-sm text-danger-11"
            >
              {submitError}
            </div>
          ) : null}
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={handleSubmit}
            disabled={!workflowId || !message.trim() || commitWorkflow.isPending}
          >
            {commitWorkflow.isPending ? "Saving..." : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
