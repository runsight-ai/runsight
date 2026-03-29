/**
 * CSS-only 3-node mini diagram representing a simple workflow.
 * Used inside the template SelectionCard on the Setup Choose screen.
 */
export function MiniDiagram() {
  return (
    <div className="flex items-center gap-2 py-3" aria-hidden="true">
      {/* Node 1 — Research */}
      <div className="flex items-center justify-center h-8 w-20 rounded bg-accent-3 text-accent-11 text-2xs font-medium node-research">
        Research
      </div>
      {/* Connector */}
      <div className="h-px w-4 bg-border-default" />
      {/* Node 2 — Write */}
      <div className="flex items-center justify-center h-8 w-20 rounded bg-accent-3 text-accent-11 text-2xs font-medium node-write">
        Write
      </div>
      {/* Connector */}
      <div className="h-px w-4 bg-border-default" />
      {/* Node 3 — Review */}
      <div className="flex items-center justify-center h-8 w-20 rounded bg-accent-3 text-accent-11 text-2xs font-medium node-review">
        Review
      </div>
    </div>
  );
}
