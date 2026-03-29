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

  const hasProviders = (providers?.items?.length ?? 0) > 0;
  const isPending = createWorkflow.isPending || updateAppSettings.isPending;

  async function handleStartBuilding() {
    try {
      const yaml = selection === "template" ? TEMPLATE_YAML : "";
      const result = await createWorkflow.mutateAsync({ yaml });
      await updateAppSettings.mutateAsync({ onboarding_completed: true });
      navigate(`/workflows/${result.id}/edit`, { replace: true });
    } catch {
      toast.error("Something went wrong. Please try again.");
    }
  }

  return (
    <main className="flex items-center justify-center min-h-screen bg-surface-primary">
      <div className="w-full max-w-[540px] px-4 py-12 flex flex-col gap-6">
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold text-heading">
            How do you want to start?
          </h1>
          <p className="text-sm text-secondary">
            You can always switch later.
          </p>
        </div>

        <div
          role="radiogroup"
          aria-label="Starting point"
          className="flex flex-col gap-3"
        >
          {/* Template card */}
          <SelectionCard
            selected={selection === "template"}
            onSelect={() => setSelection("template")}
            label="Start with a template"
          >
            <div className="flex items-center gap-2">
              <Badge variant="accent">Recommended</Badge>
              {hasProviders ? (
                <Badge variant="success">Ready to run</Badge>
              ) : (
                <Badge variant="warning">Explore mode</Badge>
              )}
            </div>
            <MiniDiagram />
          </SelectionCard>

          {/* Blank card */}
          <SelectionCard
            selected={selection === "blank"}
            onSelect={() => setSelection("blank")}
            label="Start with a blank canvas"
          >
            <EmptyCanvasPreview />
            <p className="text-sm text-secondary">
              Full block palette available
            </p>
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
