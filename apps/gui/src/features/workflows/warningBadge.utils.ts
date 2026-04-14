import type { WarningItem } from "@runsight/shared/zod";
import { WarningTooltipBody } from "@/components/shared/WarningTooltipBody";

export const WARNING_BADGE_CLASSES =
  "text-[var(--info-11)] font-medium text-xs inline-flex items-center gap-1";

export function shouldShowWarningBadge(
  warnings: WarningItem[] | undefined,
): boolean {
  return Array.isArray(warnings) && warnings.length > 0;
}

export function formatWarningTooltip(warnings: WarningItem[]): {
  header: string;
  lines: string[];
} {
  const count = warnings.length;
  const header = `${count} ${count === 1 ? "warning" : "warnings"}`;

  const lines = warnings.map((warning) => {
    const source = warning.source?.trim();
    const context = warning.context?.trim();

    if (source && context) {
      return `${warning.message} (${source}: ${context})`;
    }

    if (source) {
      return `${warning.message} (${source})`;
    }

    if (context) {
      return `${warning.message} (${context})`;
    }

    return warning.message;
  });

  return { header, lines };
}

export { WarningTooltipBody };
