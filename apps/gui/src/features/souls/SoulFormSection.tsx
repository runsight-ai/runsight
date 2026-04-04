import { useState, type ReactNode } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

interface SoulFormSectionProps {
  title: string;
  children: ReactNode;
  collapsible?: boolean;
  defaultOpen?: boolean;
}

export function SoulFormSection({
  title,
  children,
  collapsible = false,
  defaultOpen = true,
}: SoulFormSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const ChevronIcon = isOpen ? ChevronDown : ChevronRight;

  return (
    <section className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-primary)]">
      {collapsible ? (
        <button
          type="button"
          onClick={() => setIsOpen((current) => !current)}
          className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
        >
          <span className="text-sm font-semibold uppercase tracking-wider text-heading">
            {title}
          </span>
          <ChevronIcon
            className={`h-4 w-4 text-muted transition-transform ${
              isOpen ? "rotate-0" : "-rotate-90"
            }`}
          />
        </button>
      ) : (
        <header className="px-4 py-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-heading">
            {title}
          </h2>
        </header>
      )}
      {(!collapsible || isOpen) && <div className="px-4 pb-4">{children}</div>}
    </section>
  );
}

export type { SoulFormSectionProps };
