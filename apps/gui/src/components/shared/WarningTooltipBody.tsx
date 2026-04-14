import { Info } from "lucide-react";

interface WarningTooltipBodyProps {
  header: string;
  lines: string[];
}

export function WarningTooltipBody({ header, lines }: WarningTooltipBodyProps) {
  return (
    <div className="flex items-start gap-2.5">
      <Info aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-info-9" />
      <div className="min-w-0 text-sm">
        <p className="mb-1 font-medium text-primary">{header}</p>
        {lines.map((line, index) => (
          <p key={index} className="leading-5 text-secondary">{line}</p>
        ))}
      </div>
    </div>
  );
}
