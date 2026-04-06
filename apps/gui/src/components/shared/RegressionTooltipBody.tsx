import { AlertTriangle } from "lucide-react";

interface RegressionTooltipBodyProps {
  header: string;
  lines: string[];
  action?: { label: string; onClick: () => void };
}

export function RegressionTooltipBody({ header, lines, action }: RegressionTooltipBodyProps) {
  return (
    <div className="flex items-start gap-2.5">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning-9" />
      <div className="min-w-0 text-sm">
        <p className="mb-1 font-medium text-primary">{header}</p>
        {lines.map((line, index) => (
          <p key={index} className="leading-5 text-secondary">{line}</p>
        ))}
        {action && (
          <button
            type="button"
            className="mt-2 text-sm text-[var(--interactive-default)] hover:underline bg-transparent border-none cursor-pointer p-0"
            onClick={(e) => {
              e.stopPropagation();
              action.onClick();
            }}
          >
            {action.label}
          </button>
        )}
      </div>
    </div>
  );
}
