import { StatusDot } from "./src/components/ui/status-dot";
import { cn } from "./src/utils/helpers";

function getRunStatusPresentation(status: string) {
  switch (status.toLowerCase()) {
    case "completed":
    case "success":
      return { variant: "success" as const, animate: "none" as const };
    case "failed":
    case "error":
      return { variant: "danger" as const, animate: "none" as const };
    case "running":
    case "pending":
      return { variant: "warning" as const, animate: "pulse" as const };
    case "partial":
    case "paused":
    case "stalled":
      return { variant: "active" as const, animate: "none" as const };
    default:
      return { variant: "neutral" as const, animate: "none" as const };
  }
}

export function RunStatusDot({
  status,
  className,
}: {
  status: string;
  className?: string;
}) {
  const presentation = getRunStatusPresentation(status);

  return (
    <span className={cn("inline-flex items-center", className)} title={status}>
      <StatusDot
        variant={presentation.variant}
        animate={presentation.animate}
      />
      <span className="sr-only">{status}</span>
    </span>
  );
}
