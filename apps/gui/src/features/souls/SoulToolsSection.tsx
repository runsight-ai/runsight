import { Badge } from "@runsight/ui/badge";

import { SoulFormSection } from "./SoulFormSection";

type WorkflowToolContext = {
  id: string;
  label: string;
  description: string;
  enabled: boolean;
  availableInWorkflow?: boolean;
};

type AvailableTool = {
  slug: string;
  name: string;
  description: string;
  type: "builtin" | "custom" | "http";
};

interface SoulToolsSectionProps {
  tools: string[];
  workflowTools?: WorkflowToolContext[];
  availableTools?: AvailableTool[];
  onToolsChange: (tools: string[]) => void;
}

function buildAvailableTools(
  tools: string[],
  workflowTools: WorkflowToolContext[],
  availableTools: AvailableTool[],
): Array<WorkflowToolContext & { type: AvailableTool["type"] }> {
  const renderableTools = availableTools.filter((tool) => tool.slug !== "runsight/delegate");

  if (workflowTools.length > 0) {
    const workflowMap = new Map(workflowTools.map((tool) => [tool.id, tool]));
    return renderableTools.map((tool) => {
      const workflowTool = workflowMap.get(tool.slug);
      return {
        id: tool.slug,
        label: tool.name,
        description: tool.description,
        enabled: tools.includes(tool.slug),
        availableInWorkflow: workflowTool ? (workflowTool.availableInWorkflow ?? true) : false,
        type: tool.type,
      };
    });
  }

  if (renderableTools.length > 0) {
    return renderableTools.map((tool) => ({
      id: tool.slug,
      label: tool.name,
      description: tool.description,
      enabled: tools.includes(tool.slug),
      availableInWorkflow: true,
      type: tool.type,
    }));
  }

  return tools.map((tool) => ({
    id: tool,
    label: tool,
    description:
      "Enabled on this soul. Open the form from a workflow to compare workflow-only availability.",
    enabled: true,
    availableInWorkflow: true,
    type: "builtin" as const,
  }));
}

export function SoulToolsSection({
  tools,
  workflowTools = [],
  availableTools = [],
  onToolsChange,
}: SoulToolsSectionProps) {
  const toolCards = buildAvailableTools(tools, workflowTools, availableTools);
  const hasCustomTools = availableTools.some(
    (tool) => tool.slug !== "runsight/delegate" && tool.type === "custom",
  );

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

        {toolCards.length > 0 ? (
          <div className="grid gap-3 md:grid-cols-2">
            {toolCards.map((tool) => {
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
                    <div className="flex flex-wrap items-center justify-end gap-2">
                      {tool.type === "custom" ? (
                        <Badge variant="warning">Custom</Badge>
                      ) : null}
                      {selected ? (
                        <Badge variant="accent">Enabled</Badge>
                      ) : isAvailableInWorkflow ? (
                        <Badge variant="warning">Available in workflow</Badge>
                      ) : (
                        <Badge variant="warning">Not enabled in workflow</Badge>
                      )}
                    </div>
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

        {!hasCustomTools ? (
          <div className="rounded-lg border border-border-default bg-surface-secondary px-4 py-4 text-sm text-muted">
            Custom tools can be added by creating YAML files under <code>custom/tools</code>.
          </div>
        ) : null}
      </div>
    </SoulFormSection>
  );
}

export type { AvailableTool, SoulToolsSectionProps, WorkflowToolContext };
