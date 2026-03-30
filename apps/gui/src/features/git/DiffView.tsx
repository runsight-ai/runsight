import { useGitDiff } from "@/queries/git";

interface DiffViewProps {
  draft?: {
    yaml?: string;
  };
}

export function DiffView({ draft }: DiffViewProps) {
  const { data, isLoading } = useGitDiff();

  if (isLoading) {
    return (
      <div className="text-sm text-muted py-2">Loading diff...</div>
    );
  }

  if (!data?.diff) {
    if (draft?.yaml) {
      return (
        <div>
          <h4 className="text-xs font-medium text-secondary uppercase tracking-wide mb-2">
            Workflow preview
          </h4>
          <pre className="overflow-auto rounded-md border border-border-default bg-neutral-2 p-3 text-xs font-mono text-heading max-h-64">
            <code>{draft.yaml}</code>
          </pre>
        </div>
      );
    }

    return <div className="text-sm text-muted py-2">No diff available.</div>;
  }

  return (
    <div>
      <h4 className="text-xs font-medium text-secondary uppercase tracking-wide mb-2">
        Diff preview
      </h4>
      <pre className="overflow-auto rounded-md border border-border-default bg-neutral-2 p-3 text-xs font-mono text-heading max-h-64">
        <code>{data.diff}</code>
      </pre>
    </div>
  );
}
