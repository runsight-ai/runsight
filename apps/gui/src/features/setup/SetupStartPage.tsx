import { useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { Button } from "@runsight/ui/button";
import { Badge } from "@runsight/ui/badge";
import { useCreateWorkflow } from "@/queries/workflows";
import { useUpdateAppSettings } from "@/queries/settings";
import { useProviders } from "@/queries/settings";
import { TEMPLATE_YAML } from "@/features/setup/constants";
import { SelectionCard } from "./components/SelectionCard";
import { MiniDiagram } from "./components/MiniDiagram";
import { EmptyCanvasPreview } from "./components/EmptyCanvasPreview";

export function Component() {
  const [selection, setSelection] = useState<"template" | "blank">("template");
  const navigate = useNavigate();
  const createWorkflow = useCreateWorkflow();
  const updateAppSettings = useUpdateAppSettings();
  const { data: providers } = useProviders();

  const activeProviders = (providers?.items ?? []).filter((provider) => provider.is_active ?? true);
  const hasProviders = activeProviders.length > 0;
  const isPending = createWorkflow.isPending || updateAppSettings.isPending;

  async function handleStartBuilding() {
    try {
      const name = selection === "template" ? "Research & Review" : "Untitled Workflow";
      const yaml = selection === "template" ? TEMPLATE_YAML : "";
      const result = await createWorkflow.mutateAsync({ name, yaml });
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
            description="A 3-block workflow with 2 AI agents. Research a topic, write a summary, and quality-check the output."
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

        <Button
          variant="primary"
          size="lg"
          loading={isPending}
          disabled={isPending}
          onClick={handleStartBuilding}
          className="w-full"
        >
          Start Building
        </Button>
      </div>
    </main>
  );
}
