import { useParams } from "react-router";

export function Component() {
  const { id } = useParams();

  return (
    <div className="p-6">
      <h1 className="text-2xl font-semibold text-[var(--foreground)]">Workflow Canvas</h1>
      <p className="mt-2 text-sm text-[var(--muted-foreground)]">
        Canvas module is available. Workflow ID: {id ?? "unknown"}.
      </p>
    </div>
  );
}

