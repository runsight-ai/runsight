import { Button } from "@runsight/ui/button";

interface SoulFormFooterProps {
  mode: "create" | "edit";
  returnUrl: string | null;
  isDirty: boolean;
  isSubmitting: boolean;
  isValid: boolean;
  onCancel: () => void;
  onSubmit: () => void;
}

export function SoulFormFooter({
  mode,
  returnUrl,
  isDirty,
  isSubmitting,
  isValid,
  onCancel,
  onSubmit,
}: SoulFormFooterProps) {
  const submitLabel = returnUrl
    ? "Save & Return to Canvas"
    : mode === "create"
      ? "Create Soul"
      : "Save Changes";

  const submitDisabled = isSubmitting || !isValid || (mode === "edit" && !isDirty);

  return (
    <footer className="sticky bottom-0 border-t border-[var(--border-subtle)] bg-[var(--surface-primary)]">
      <div className="mx-auto flex max-w-2xl items-center justify-end gap-3 px-6 py-4">
        <Button variant="ghost" onClick={onCancel} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button variant="primary" onClick={onSubmit} disabled={submitDisabled}>
          {submitLabel}
        </Button>
      </div>
    </footer>
  );
}

export type { SoulFormFooterProps };
