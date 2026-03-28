import { cn } from "@/utils/helpers";
import { ChevronLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  breadcrumbs?: React.ReactNode;
  backHref?: string;
  onBack?: () => void;
  actions?: React.ReactNode;
  className?: string;
}

export function PageHeader({
  title,
  subtitle,
  breadcrumbs,
  backHref,
  onBack,
  actions,
  className,
}: PageHeaderProps) {
  const showBack = backHref || onBack;

  return (
    <div
      className={cn(
        "flex h-[var(--header-height)] items-center justify-between border-b border-border-default px-4",
        className
      )}
    >
      <div className="flex items-center gap-3">
        {showBack && (
          <>
            {backHref ? (
              <a href={backHref}>
                <Button variant="ghost" size="icon-sm">
                  <ChevronLeft className="h-4 w-4" />
                </Button>
              </a>
            ) : (
              <Button variant="ghost" size="icon-sm" onClick={onBack}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
            )}
          </>
        )}
        <div className="flex flex-col">
          {breadcrumbs && (
            <div className="text-xs text-muted">{breadcrumbs}</div>
          )}
          <h1 className="text-base font-medium leading-tight text-primary">
            {title}
          </h1>
          {subtitle && (
            <span className="text-xs text-muted">{subtitle}</span>
          )}
        </div>
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
