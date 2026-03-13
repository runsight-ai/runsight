import { useState, useCallback, useEffect } from "react";
import type { FileChange, FileChangeType } from "@/queries/workflows";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  X,
  Check,
  Sparkles,
  ExternalLink,
  AlertCircle,
} from "lucide-react";

// Re-export types from queries/workflows for convenience
export type { FileChange, FileChangeType };

export interface DiffLine {
  type: "added" | "removed" | "unchanged";
  lineNumber: number;
  content: string;
}

export interface DiffPreview {
  lines: DiffLine[];
  fileName: string;
}

interface CommitModalProps {
  isOpen: boolean;
  onClose: () => void;
  workflowName: string;
  changedFiles: FileChange[];
  diffPreview?: DiffPreview;
  onCommit: (message: string) => Promise<void>;
  onAiSuggest?: () => Promise<string>;
  onViewFullDiff?: () => void;
  isCommitting?: boolean;
  errorMessage?: string | null;
}

const STATUS_COLORS: Record<FileChangeType, string> = {
  M: "text-[#F5A623]", // Modified - amber
  A: "text-[#28A745]", // Added - green
  D: "text-[#E53935]", // Deleted - red
};

const STATUS_LABELS: Record<FileChangeType, string> = {
  M: "Modified",
  A: "Added",
  D: "Deleted",
};

export function CommitModal({
  isOpen,
  onClose,
  workflowName,
  changedFiles,
  diffPreview,
  onCommit,
  onAiSuggest,
  onViewFullDiff,
  isCommitting = false,
  errorMessage,
}: CommitModalProps) {
  const [commitMessage, setCommitMessage] = useState(`feat(workflow): update ${workflowName}`);
  const [isGeneratingMessage, setIsGeneratingMessage] = useState(false);
  const [aiSuggestError, setAiSuggestError] = useState<string | null>(null);

  // Reset message and errors when modal opens
  useEffect(() => {
    if (isOpen) {
      setAiSuggestError(null);
    }
  }, [isOpen]);

  const handleOpenChange = useCallback((open: boolean) => {
    if (!open) {
      onClose();
    }
  }, [onClose]);

  const handleCommit = useCallback(async () => {
    if (!commitMessage.trim() || isCommitting) return;
    await onCommit(commitMessage);
  }, [commitMessage, onCommit, isCommitting]);

  const handleAiSuggest = useCallback(async () => {
    if (!onAiSuggest || isGeneratingMessage) return;
    setIsGeneratingMessage(true);
    setAiSuggestError(null);
    try {
      const suggestedMessage = await onAiSuggest();
      setCommitMessage(suggestedMessage);
    } catch (err) {
      setAiSuggestError(err instanceof Error ? err.message : "Failed to generate suggestion");
    } finally {
      setIsGeneratingMessage(false);
    }
  }, [onAiSuggest, isGeneratingMessage]);

  const isCommitDisabled = !commitMessage.trim() || isCommitting;

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="w-[560px] max-h-[80vh] p-0 overflow-hidden bg-[#16161C] border-[#2D2D35] rounded-xl">
        {/* Header */}
        <DialogHeader className="h-14 px-4 flex flex-row items-center justify-between border-b border-[#2D2D35] !pb-0 !m-0">
          <DialogTitle className="text-base font-medium text-[#EDEDF0]">
            Commit Workflow Changes
          </DialogTitle>
          <Button
            variant="ghost"
            size="icon-sm"
            className="w-8 h-8 text-[#9292A0] hover:text-[#EDEDF0] hover:bg-[#22222A]"
            onClick={onClose}
            disabled={isCommitting}
          >
            <X className="w-4 h-4" />
            <span className="sr-only">Close</span>
          </Button>
        </DialogHeader>

        {/* Body */}
        <div className="flex-1 overflow-auto p-4 space-y-4">
          {/* Commit error message */}
          {errorMessage && (
            <div
              className="flex items-center gap-2 px-3 py-2 rounded-md bg-[#E53935]/10 border border-[#E53935]/30 text-sm text-[#E53935]"
              role="alert"
            >
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* AI Suggest error message */}
          {aiSuggestError && (
            <div
              className="flex items-center gap-2 px-3 py-2 rounded-md bg-[#E53935]/10 border border-[#E53935]/30 text-sm text-[#E53935]"
              role="alert"
            >
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{aiSuggestError}</span>
            </div>
          )}

          {/* Changed Files List */}
          <div>
            <label className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] block mb-2">
              Changed files ({changedFiles.length})
            </label>
            <div className="bg-[#0D0D12] border border-[#2D2D35] rounded-md p-3 space-y-1.5 max-h-[180px] overflow-auto">
              {changedFiles.length === 0 ? (
                <div className="text-sm text-[#9292A0] text-center py-4">
                  No changes to commit
                </div>
              ) : (
                changedFiles.map((file, index) => (
                  <div
                    key={`${file.path}-${index}`}
                    className="flex items-center gap-3 py-1"
                  >
                    <span
                      className={`w-6 text-center font-mono text-[13px] font-medium ${STATUS_COLORS[file.type]}`}
                      title={STATUS_LABELS[file.type]}
                    >
                      {file.type}
                    </span>
                    <span className="flex-1 font-mono text-[13px] text-[#EDEDF0] truncate">
                      {file.path}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* View Full Diff Link */}
          {onViewFullDiff && changedFiles.length > 0 && (
            <div>
              <Button
                variant="ghost"
                size="sm"
                className="flex items-center gap-2 text-[#5E6AD2] hover:text-[#717EE3] hover:bg-[#5E6AD2]/10 h-8 px-2 -ml-2"
                onClick={onViewFullDiff}
              >
                <span className="text-sm">View Full Diff</span>
                <ExternalLink className="w-4 h-4" />
              </Button>
            </div>
          )}

          {/* Commit Message */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B]">
                Commit message
              </label>
              {onAiSuggest && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="flex items-center gap-1.5 text-[#5E6AD2] hover:text-[#717EE3] hover:bg-[#5E6AD2]/10 h-7 px-2"
                  onClick={handleAiSuggest}
                  disabled={isGeneratingMessage || isCommitting}
                >
                  <Sparkles className="w-4 h-4" />
                  <span className="text-sm">
                    {isGeneratingMessage ? "Generating..." : "AI Suggest"}
                  </span>
                </Button>
              )}
            </div>
            <Textarea
              value={commitMessage}
              onChange={(e) => setCommitMessage(e.target.value)}
              placeholder="Enter a descriptive commit message..."
              className="min-h-[80px] bg-[#0D0D12] border-[#2D2D35] rounded-md text-sm text-[#EDEDF0] placeholder:text-[#5E5E6B] resize-y focus:border-[#5E6AD2] focus:ring-1 focus:ring-[#5E6AD2]/50"
              disabled={isCommitting}
            />
            <p className="text-xs text-[#5E5E6B] mt-1.5">
              Follow conventional commits format: type(scope): description
            </p>
          </div>

          {/* Mini Diff Preview */}
          {diffPreview && diffPreview.lines.length > 0 && (
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5E5E6B] block mb-2">
                Preview - {diffPreview.fileName}
              </label>
              <div className="bg-[#0D0D12] border border-[#2D2D35] rounded-md p-3 font-mono text-[12px] leading-relaxed max-h-[140px] overflow-auto">
                <div className="flex">
                  <div className="text-[#5E5E6B] select-none pr-3 text-right w-8">
                    {diffPreview.lines.map((line, i) => (
                      <div key={i}>{line.lineNumber}</div>
                    ))}
                  </div>
                  <div className="flex-1">
                    {diffPreview.lines.map((line, i) => (
                      <div
                        key={i}
                        className={
                          line.type === "added"
                            ? "text-[#28A745]"
                            : line.type === "removed"
                            ? "text-[#E53935] line-through opacity-50"
                            : "text-[#EDEDF0]"
                        }
                      >
                        <span className="select-none mr-2">
                          {line.type === "added"
                            ? "+"
                            : line.type === "removed"
                            ? "-"
                            : " "}
                        </span>
                        <span>{line.content}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <DialogFooter className="h-16 px-4 flex flex-row items-center justify-end gap-3 border-t border-[#2D2D35] !py-0 !mt-0">
          <Button
            variant="outline"
            className="h-9 px-4 border-[#3F3F4A] bg-transparent text-[#EDEDF0] hover:bg-[#22222A]"
            onClick={onClose}
            disabled={isCommitting}
          >
            Cancel
          </Button>
          <Button
            className="h-9 px-4 bg-[#5E6AD2] text-white hover:bg-[#717EE3] active:bg-[#4F5ABF] active:scale-[0.98] flex items-center gap-2"
            onClick={handleCommit}
            disabled={isCommitDisabled}
          >
            {isCommitting ? (
              <>
                <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                Committing...
              </>
            ) : (
              <>
                <Check className="w-4 h-4" />
                Commit Changes
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
