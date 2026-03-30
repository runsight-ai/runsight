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
      <div
        className="flex items-center gap-2 text-sm text-secondary py-1"
        role="status"
        aria-live="polite"
      >
        <Loader2 className="size-3.5 animate-spin shrink-0" strokeWidth={2} />
        <span>Testing connection...</span>
      </div>
    );
  }

  if (status === "success") {
    return (
      <div
        className="flex items-center gap-2 text-sm text-success py-1"
        role="status"
        aria-live="polite"
      >
        <Check className="size-3.5 shrink-0" strokeWidth={2.5} />
        <span>
          Connected{modelCount != null && modelCount > 0 ? ` \u2014 ${modelCount} models available` : ""}
        </span>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div
        className="flex items-center gap-2 text-sm text-danger py-1"
        role="status"
        aria-live="polite"
      >
        <XCircle className="size-3.5 shrink-0" strokeWidth={2.5} />
        <span>{message || "Invalid key. Check that you copied the full key from your provider dashboard."}</span>
      </div>
    );
  }

  return null;
}
