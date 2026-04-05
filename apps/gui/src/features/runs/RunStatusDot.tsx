import { cn } from "@runsight/ui/utils";

export function getRunStatusTone(status: string) {
  switch (status.toLowerCase()) {
    case "completed":
    case "success":
      return "success";
    case "failed":
    case "error":
      return "danger";
    case "killed":
      return "neutral";
    case "running":
    case "pending":
      return "running";
    case "partial":
    case "paused":
    case "stalled":
      return "info";
    default:
      return "neutral";
  }
}

export function RunStatusDot({
  status,
  className,
}: {
  status: string;
  className?: string;
}) {
  const tone = getRunStatusTone(status);

  return (
    <span className={cn("inline-flex items-center", className)} title={status}>
      <span
        aria-hidden="true"
        className={cn(
          "size-2 rounded-full",
          tone === "success" && "bg-success-9",
          tone === "danger" && "bg-danger-9",
          tone === "neutral" && "bg-neutral-7",
          tone === "info" && "bg-info-9",
          tone === "running" && "bg-warning-9 animate-[pulse_2s_ease-in-out_infinite]",
        )}
      />
      <span className="sr-only">{status}</span>
    </span>
  );
}
