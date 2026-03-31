import { PageHeader } from "@/components/shared";
import { RunsTab } from "@/features/flows/RunsTab";

export function Component() {
  return (
    <div className="flex h-full flex-col bg-surface-primary">
      <PageHeader title="Runs" />

      <main className="flex-1 overflow-auto px-6 pb-6">
        <RunsTab />
      </main>
    </div>
  );
}
