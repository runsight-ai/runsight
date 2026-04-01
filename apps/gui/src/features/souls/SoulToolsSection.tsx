import { Badge } from "@runsight/ui/badge";

import { SoulFormSection } from "./SoulFormSection";

type WorkflowToolContext = {
  id: string;
  label: string;
  description: string;
  enabled: boolean;
  availableInWorkflow?: boolean;
};

interface SoulToolsSectionProps {
  tools: string[];
  workflowTools?: WorkflowToolContext[];
  onToolsChange: (tools: string[]) => void;
}

function buildAvailableTools(
  tools: string[],
  workflowTools: WorkflowToolContext[],
): WorkflowToolContext[] {
  if (workflowTools.length > 0) {
    return workflowTools;
  }

  return tools.map((tool) => ({
    id: tool,
    label: tool,
    description:
      "Enabled on this soul. Open the form from a workflow to compare workflow-only availability.",
    enabled: true,
  }));
}

export function SoulToolsSection({
  tools,
  workflowTools = [],
  onToolsChange,
}: SoulToolsSectionProps) {
  const availableTools = buildAvailableTools(tools, workflowTools);

  const toggleTool = (toolId: string) => {
    const nextTools = tools.includes(toolId)
      ? tools.filter((tool) => tool !== toolId)
      : [...tools, toolId];

    onToolsChange(nextTools);
  };

  return (
    <SoulFormSection title="Tools" collapsible defaultOpen={false}>
      <div className="space-y-4">
        <div className="space-y-2">
          <p className="text-sm text-secondary">
            Workflow tools define what this soul can use in the current editor context.
          </p>
          <p className="text-sm text-muted">
            Tools marked as available in this workflow stay informational until you enable
            them on the soul. Delegate and other workflow-only mechanics are governed here
            instead of by a hardcoded assignable picker.
          </p>
        </div>

        {availableTools.length > 0 ? (
          <div className="grid gap-3 md:grid-cols-2">
            {availableTools.map((tool) => {
              const selected = tools.includes(tool.id);
              const isAvailableInWorkflow = tool.availableInWorkflow !== false;

              return (
                <button
                  key={tool.id}
                  type="button"
                  onClick={() => toggleTool(tool.id)}
                  className={[
                    "rounded-lg border px-4 py-4 text-left transition",
                    selected
                      ? "border-accent-8 bg-accent-3/20 shadow-[0_0_0_1px_var(--accent-8)]"
                      : "border-border-default bg-surface-secondary hover:border-border-strong",
                  ].join(" ")}
                  aria-pressed={selected}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-medium text-heading">{tool.label}</div>
                      <div className="mt-1 text-sm text-muted">{tool.description}</div>
                    </div>
                    {selected ? (
                      <Badge variant="accent">Enabled</Badge>
                    ) : isAvailableInWorkflow ? (
                      <Badge variant="warning">Available in workflow</Badge>
                    ) : (
                      <Badge variant="warning">Not enabled in workflow</Badge>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        ) : (
          <div className="rounded-lg border border-border-default bg-surface-secondary px-4 py-4 text-sm text-muted">
            Open this form from a workflow to compare available tools and enable them on
            the soul.
          </div>
        )}
      </div>
    </SoulFormSection>
  );
}

export type { SoulToolsSectionProps, WorkflowToolContext };
