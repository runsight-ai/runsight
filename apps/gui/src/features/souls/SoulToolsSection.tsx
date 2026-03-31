import { Badge } from "@runsight/ui/badge";
import { Button } from "@runsight/ui/button";

import { SoulFormSection } from "./SoulFormSection";

interface SoulToolsSectionProps {
  tools: string[];
  onToolsChange: (tools: string[]) => void;
}

const ASSIGNABLE_SOUL_TOOLS = [
  {
    value: "runsight/http",
    label: "HTTP Requests",
    description: "Let this soul fetch web pages and call external APIs.",
  },
  {
    value: "runsight/file-io",
    label: "Workspace Files",
    description: "Let this soul read and write files in the workspace.",
  },
] as const;

const HIDDEN_SYSTEM_TOOLS = new Set(["runsight/delegate"]);

export function SoulToolsSection({ tools, onToolsChange }: SoulToolsSectionProps) {
  const assignableToolValues = new Set(ASSIGNABLE_SOUL_TOOLS.map((tool) => tool.value));
  const selectedAssignableTools = tools.filter((tool) => assignableToolValues.has(tool));
  const hiddenTools = tools.filter((tool) => HIDDEN_SYSTEM_TOOLS.has(tool));
  const legacyTools = tools.filter(
    (tool) => !assignableToolValues.has(tool) && !HIDDEN_SYSTEM_TOOLS.has(tool),
  );

  const toggleTool = (toolValue: string) => {
    const nextAssignableTools = selectedAssignableTools.includes(toolValue)
      ? selectedAssignableTools.filter((tool) => tool !== toolValue)
      : [...selectedAssignableTools, toolValue];

    onToolsChange([...legacyTools, ...hiddenTools, ...nextAssignableTools]);
  };

  const removeLegacyTool = (toolValue: string) => {
    onToolsChange(tools.filter((tool) => tool !== toolValue));
  };

  return (
    <SoulFormSection title="Tools" collapsible defaultOpen={false}>
      <div className="space-y-4">
        <div className="space-y-2">
          <p className="text-sm text-secondary">
            Choose the user-facing tools this soul should carry with it across workflows.
          </p>
          <p className="text-sm text-muted">
            System mechanics like delegate are assigned automatically by block/runtime
            behavior and do not appear in soul settings.
          </p>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          {ASSIGNABLE_SOUL_TOOLS.map((tool) => {
            const selected = selectedAssignableTools.includes(tool.value);

            return (
              <button
                key={tool.value}
                type="button"
                onClick={() => toggleTool(tool.value)}
                className={[
                  "rounded-lg border px-4 py-4 text-left transition",
                  selected
                    ? "border-accent-8 bg-accent-3/20 shadow-[0_0_0_1px_var(--accent-8)]"
                    : "border-border-default bg-surface-secondary hover:border-border-strong",
                ].join(" ")}
                aria-pressed={selected}
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-heading">{tool.label}</div>
                    <div className="mt-1 text-sm text-muted">{tool.description}</div>
                  </div>
                  {selected ? <Badge variant="accent">Enabled</Badge> : null}
                </div>
              </button>
            );
          })}
        </div>

        {legacyTools.length > 0 ? (
          <div className="space-y-2">
            <p className="text-xs font-medium uppercase tracking-wide text-muted">
              Existing custom refs
            </p>
            <div className="flex flex-wrap gap-2">
              {legacyTools.map((tool) => (
                <div key={tool} className="flex items-center gap-2 rounded-full border border-border-default bg-surface-secondary px-3 py-1">
                  <Badge variant="outline">{tool}</Badge>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => removeLegacyTool(tool)}
                    className="h-auto px-1 py-0 text-xs text-muted hover:text-heading"
                  >
                    Remove
                  </Button>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="rounded-md border border-dashed border-border-default bg-surface-secondary px-4 py-3 text-sm text-muted">
            This soul has no tools enabled yet.
          </div>
        )}
      </div>
    </SoulFormSection>
  );
}

export type { SoulToolsSectionProps };
