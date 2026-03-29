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
      <div className="flex items-center gap-2 text-[13px] text-[var(--text-muted)]">
        <Loader2 className="size-4 animate-spin" strokeWidth={2} />
        <span>Testing connection...</span>
      </div>
    );
  }

  if (status === "success") {
    return (
      <div className="flex items-center gap-2 text-[13px] text-[var(--success-9)]">
        <Check className="size-4" strokeWidth={2} />
        <span>
          Connected{modelCount != null && modelCount > 0 ? ` \u00b7 ${modelCount} models` : ""}
        </span>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="flex items-center gap-2 text-[13px] text-[var(--danger-9)]">
        <XCircle className="size-4" strokeWidth={2} />
        <span>{message || "Connection failed"}</span>
      </div>
    );
  }

  return null;
}
