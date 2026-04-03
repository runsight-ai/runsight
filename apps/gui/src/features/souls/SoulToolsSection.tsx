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
  id: string;
  name: string;
  description: string;
  origin: string;
  executor: string;
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
): Array<
  WorkflowToolContext & {
    origin?: string;
    executor?: string;
  }
> {
  const visibleToolIds = new Set<string>();
  const workflowMap = new Map(
    workflowTools
      .filter((tool) => tool.id !== "delegate")
      .map((tool) => [tool.id, tool]),
  );
  const availableToolMap = new Map(
    availableTools
      .filter((tool) => tool.id !== "delegate")
      .map((tool) => [tool.id, tool]),
  );

  workflowTools.forEach((tool) => {
    if (tool.id !== "delegate") {
      visibleToolIds.add(tool.id);
    }
  });
  availableTools.forEach((tool) => {
    if (tool.id !== "delegate") {
      visibleToolIds.add(tool.id);
    }
  });
  tools.forEach((toolId) => {
    if (toolId !== "delegate") {
      visibleToolIds.add(toolId);
    }
  });

  return [...visibleToolIds].map((toolId) => {
    const workflowTool = workflowMap.get(toolId);
    const availableTool = availableToolMap.get(toolId);

    return {
      id: toolId,
      label: availableTool?.name ?? workflowTool?.label ?? toolId,
      description:
        availableTool?.description ??
        workflowTool?.description ??
        "Enabled on this soul. Open the form from a workflow to compare workflow-only availability.",
      enabled: tools.includes(toolId),
      availableInWorkflow:
        workflowTool != null ? (workflowTool.availableInWorkflow ?? true) : workflowTools.length === 0,
      origin: availableTool?.origin,
      executor: availableTool?.executor,
    };
  });
}

function formatMetadataLabel(value: string, kind: "origin" | "executor"): string {
  const normalized = value.trim().toLowerCase();

  if (kind === "origin") {
    if (normalized === "builtin") {
      return "Built-in";
    }
    if (normalized === "custom") {
      return "Custom";
    }
  }

  if (kind === "executor") {
    if (normalized === "native") {
      return "Native";
    }
    if (normalized === "python") {
      return "Python";
    }
    if (normalized === "request") {
      return "Request";
    }
  }

  return value
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function SoulToolsSection({
  tools,
  workflowTools = [],
  availableTools = [],
  onToolsChange,
}: SoulToolsSectionProps) {
  const toolCards = buildAvailableTools(tools, workflowTools, availableTools);
  const hasCustomTools = availableTools.some(
    (tool) => tool.id !== "delegate" && tool.origin === "custom",
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
              const shouldShowOrigin = Boolean(tool.origin && tool.origin !== "builtin");
              const shouldShowExecutor = Boolean(tool.executor && tool.executor !== "native");

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
                      {shouldShowOrigin ? (
                        <Badge variant="outline">
                          {formatMetadataLabel(tool.origin!, "origin")}
                        </Badge>
                      ) : null}
                      {shouldShowExecutor ? (
                        <Badge variant="outline">
                          {formatMetadataLabel(tool.executor!, "executor")}
                        </Badge>
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
