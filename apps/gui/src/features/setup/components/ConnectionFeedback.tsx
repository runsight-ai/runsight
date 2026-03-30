import type { TestStatus } from "@/components/provider";
import { Loader2, Check, XCircle } from "lucide-react";

interface ConnectionFeedbackProps {
  status: TestStatus;
  message?: string;
  modelCount?: number;
}

export function ConnectionFeedback({ status, message, modelCount }: ConnectionFeedbackProps) {
  if (status === "idle") return null;

  if (status === "testing") {
    return (
      <div className="flex items-center gap-[var(--space-2)] text-[var(--font-size-sm)] text-[var(--text-secondary)] py-[var(--space-1)]">
        <Loader2 className="size-3.5 animate-spin shrink-0" strokeWidth={2} />
        <span>Testing connection...</span>
      </div>
    );
  }

  if (status === "success") {
    return (
      <div className="flex items-center gap-[var(--space-2)] text-[var(--font-size-sm)] text-[var(--state-success)] py-[var(--space-1)]">
        <Check className="size-3.5 shrink-0" strokeWidth={2.5} />
        <span>
          Connected{modelCount != null && modelCount > 0 ? ` \u2014 ${modelCount} models available` : ""}
        </span>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="flex items-center gap-[var(--space-2)] text-[var(--font-size-sm)] text-[var(--state-error)] py-[var(--space-1)]">
        <XCircle className="size-3.5 shrink-0" strokeWidth={2.5} />
        <span>{message || "Invalid key. Check that you copied the full key from your provider dashboard."}</span>
      </div>
    );
  }

  return null;
}
