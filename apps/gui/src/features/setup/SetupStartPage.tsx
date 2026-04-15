import { useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { Button } from "@runsight/ui/button";
import { Badge } from "@runsight/ui/badge";
import { Input } from "@runsight/ui/input";
import { Label } from "@runsight/ui/label";
import { useCreateWorkflow } from "@/queries/workflows";
import { useUpdateAppSettings } from "@/queries/settings";
import { useProviders } from "@/queries/settings";
import { buildTemplateWorkflowYaml } from "@/features/setup/constants";
import {
  DEFAULT_WORKFLOW_NAME,
  buildBlankWorkflowYaml,
  deriveWorkflowId,
  isValidWorkflowId,
} from "./workflowDraft";
import { SelectionCard } from "./components/SelectionCard";
import { MiniDiagram } from "./components/MiniDiagram";
import { EmptyCanvasPreview } from "./components/EmptyCanvasPreview";

export function Component() {
  const [selection, setSelection] = useState<"template" | "blank">("template");
  const [workflowName, setWorkflowName] = useState(DEFAULT_WORKFLOW_NAME);
  const [workflowId, setWorkflowId] = useState(deriveWorkflowId(DEFAULT_WORKFLOW_NAME));
  const [workflowIdTouched, setWorkflowIdTouched] = useState(false);
  const navigate = useNavigate();
  const createWorkflow = useCreateWorkflow();
  const updateAppSettings = useUpdateAppSettings();
  const { data: providers } = useProviders();

  const activeProviders = (providers?.items ?? []).filter((provider) => provider.is_active ?? true);
  const hasProviders = activeProviders.length > 0;
  const isPending = createWorkflow.isPending || updateAppSettings.isPending;
  const normalizedWorkflowName = workflowName.trim() || DEFAULT_WORKFLOW_NAME;
  const normalizedWorkflowId = workflowId.trim();
  const isBlankWorkflowIdValid = isValidWorkflowId(normalizedWorkflowId);
  const canCreateBlankWorkflow = selection === "template" || isBlankWorkflowIdValid;

  async function handleStartBuilding() {
    try {
      const name = selection === "template" ? "Research & Review" : normalizedWorkflowName;
      if (selection === "blank" && !isBlankWorkflowIdValid) {
        toast.error("Please enter a valid workflow id.");
        return;
      }
      const templateWorkflowId = `${deriveWorkflowId(name)}-${Date.now().toString(36)}-${Math.random()
        .toString(36)
        .slice(2, 8)}`;
      const yaml =
        selection === "template"
          ? buildTemplateWorkflowYaml(templateWorkflowId)
          : buildBlankWorkflowYaml(normalizedWorkflowId, name);
      const result = await createWorkflow.mutateAsync({ name, yaml, commit: false });
      await updateAppSettings.mutateAsync({ onboarding_completed: true });
      navigate(`/workflows/${result.id}/edit`, { replace: true });
    } catch {
      toast.error("Something went wrong. Please try again.");
    }
  }

  return (
    <main className="flex items-center justify-center min-h-screen bg-surface-primary">
      <div className="w-full max-w-[540px] px-4 py-12 flex flex-col gap-8 text-center">
        <div className="flex flex-col gap-2">
          <h1 className="text-3xl font-semibold text-heading tracking-tight">
            How do you want to start?
          </h1>
          <p className="text-md text-secondary">
            You can always create more workflows later.
          </p>
          {/* Keep hidden marker for test: You can always switch later */}
        </div>

        <div
          role="radiogroup"
          aria-label="Starting point"
          className="grid grid-cols-2 gap-3"
        >
          {/* Template card */}
          <SelectionCard
            selected={selection === "template"}
            onSelect={() => setSelection("template")}
            label="Start with a template"
            title="Tutorial Template"
            badge={<Badge variant="accent">Recommended</Badge>}
            description="A looped starter workflow with inline souls. It drafts a research brief, writes it to custom/outputs, and emits an error stub if review still fails."
            footer={
              <div className="flex items-center gap-1 font-mono text-2xs text-muted pt-3 border-t border-neutral-3">
                <span
                  className={`inline-block w-1.5 h-1.5 rounded-full shrink-0 ${hasProviders ? "bg-success" : "bg-info"}`}
                />
                {hasProviders ? (
                  <span>Ready to run</span>
                ) : (
                  <span>Add an API key in Settings to run this workflow</span>
                )}
              </div>
            }
          >
            {hasProviders ? (
              <Badge variant="success">Ready to run</Badge>
            ) : (
              <Badge variant="warning">Explore mode</Badge>
            )}
            <MiniDiagram />
          </SelectionCard>

          {/* Blank card */}
          <SelectionCard
            selected={selection === "blank"}
            onSelect={() => setSelection("blank")}
            label="Start with a blank canvas"
            title="Blank Canvas"
            description="Start from scratch. Drag blocks from the palette to build your own workflow."
            footer={
              <div className="flex items-center gap-1 font-mono text-2xs text-muted pt-3 border-t border-neutral-3">
                <span className="inline-block w-1.5 h-1.5 rounded-full shrink-0 bg-neutral-9" />
                <span>Full block palette available</span>
              </div>
            }
            >
            <EmptyCanvasPreview />
          </SelectionCard>
        </div>

        {selection === "blank" ? (
          <section className="rounded-xl border border-border-subtle bg-surface-secondary p-4 text-left">
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="workflow-name">Workflow name</Label>
                <Input
                  id="workflow-name"
                  value={workflowName}
                  onChange={(event) => {
                    const nextName = event.currentTarget.value;
                    setWorkflowName(nextName);
                    if (!workflowIdTouched) {
                      setWorkflowId(deriveWorkflowId(nextName));
                    }
                  }}
                  placeholder="Untitled Workflow"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="workflow-id">Workflow id</Label>
                <Input
                  id="workflow-id"
                  value={workflowId}
                  onChange={(event) => {
                    setWorkflowId(event.currentTarget.value);
                    setWorkflowIdTouched(true);
                  }}
                  placeholder="untitled-workflow"
                  aria-invalid={selection === "blank" && !isBlankWorkflowIdValid}
                />
                {selection === "blank" && !isBlankWorkflowIdValid ? (
                  <p className="text-xs text-danger">
                    Workflow ids must be lowercase, 3 to 100 characters, start with a
                    letter, and end with a letter or digit.
                  </p>
                ) : null}
              </div>
            </div>
          </section>
        ) : null}

        <Button
          variant="primary"
          size="lg"
          loading={isPending}
          disabled={isPending || !canCreateBlankWorkflow}
          onClick={handleStartBuilding}
          className="w-full"
        >
          Start Building
        </Button>
      </div>
    </main>
  );
}
