/**
 * CSS-only 3-node mini diagram representing a simple workflow.
 * Used inside the template SelectionCard on the Setup Choose screen.
 *
 * Each node has a colored top border (agent=blue, logic=violet) and a label.
 * Nodes are connected by arrow edges.
 */

const NODES: { label: string; category: "agent" | "logic" }[] = [
  { label: "Research", category: "agent" },
  { label: "Write", category: "agent" },
  { label: "Review", category: "logic" },
];

const CATEGORY_COLOR: Record<string, string> = {
  agent: "bg-block-agent",
  logic: "bg-block-logic",
};

function MiniNode({ label, category }: { label: string; category: "agent" | "logic" }) {
  return (
    <div className="flex flex-col items-center gap-0.5 w-16 node-mini">
      {/* Node box with colored top border */}
      <div className="relative w-14 h-8 rounded-sm border border-border-subtle bg-surface-secondary overflow-hidden">
        <div className={`absolute top-0 left-0 right-0 h-[3px] ${CATEGORY_COLOR[category]}`} />
      </div>
      {/* Node label */}
      <span className="font-mono text-[9px] text-muted uppercase tracking-wide">
        {label}
      </span>
    </div>
  );
}

function MiniEdge() {
  return (
    <div className="relative w-4 h-px bg-neutral-7 -mt-2.5">
      {/* Arrow head */}
      <div
        className="absolute -right-px -top-[3px] w-0 h-0"
        style={{
          borderLeft: "4px solid var(--neutral-7)",
          borderTop: "3px solid transparent",
          borderBottom: "3px solid transparent",
        }}
      />
    </div>
  );
}

export function MiniDiagram() {
  return (
    <div
      className="flex items-center justify-center gap-1.5 py-4 px-2 bg-surface-primary rounded-md border border-neutral-3"
      aria-hidden="true"
    >
      {NODES.map((node, i) => (
        <div key={node.label} className="contents">
          {i > 0 && <MiniEdge />}
          <MiniNode label={node.label} category={node.category} />
        </div>
      ))}
    </div>
  );
}
