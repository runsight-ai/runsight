import { cn } from "@/utils/helpers";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface CostDisplayProps {
  cost: number;
  isEstimate?: boolean;
  showTooltip?: boolean;
  tooltipContent?: React.ReactNode;
  className?: string;
}

export function CostDisplay({
  cost,
  isEstimate = false,
  showTooltip = false,
  tooltipContent,
  className,
}: CostDisplayProps) {
  const formattedCost = cost.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 4,
    maximumFractionDigits: 4,
  });

  const displayValue = isEstimate ? `~${formattedCost}` : formattedCost;

  const content = (
    <span
      className={cn(
        "font-mono text-xs",
        isEstimate ? "text-muted-foreground" : "text-secondary-foreground",
        className
      )}
    >
      {displayValue}
    </span>
  );

  if (showTooltip && tooltipContent) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger>{content}</TooltipTrigger>
          <TooltipContent>{tooltipContent}</TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return content;
}
