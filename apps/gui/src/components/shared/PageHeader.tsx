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
        "flex items-start justify-between px-6 py-6",
        className
      )}
    >
      <div className="flex items-start gap-3">
        {showBack && (
          <>
            {backHref ? (
              <a href={backHref} className="mt-1">
                <Button variant="ghost" size="icon-sm">
                  <ChevronLeft className="h-4 w-4" />
                </Button>
              </a>
            ) : (
              <Button variant="ghost" size="icon-sm" onClick={onBack} className="mt-1">
                <ChevronLeft className="h-4 w-4" />
              </Button>
            )}
          </>
        )}
        <div className="flex flex-col">
          {breadcrumbs && (
            <div className="text-xs text-muted mb-1">{breadcrumbs}</div>
          )}
          <h1 className="text-lg font-semibold leading-tight text-primary">
            {title}
          </h1>
          {subtitle && (
            <p className="text-[length:var(--font-size-md)] text-muted mt-1">{subtitle}</p>
          )}
        </div>
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
