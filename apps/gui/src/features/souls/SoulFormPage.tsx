import { useEffect } from "react";
import {
  useBlocker,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router";
import { parse } from "yaml";

import { PageHeader } from "@/components/shared/PageHeader";
import { useAvailableTools, useSoul } from "@/queries/souls";
import { useWorkflow } from "@/queries/workflows";
import { Button } from "@runsight/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from "@runsight/ui/dialog";

import type { AvailableTool, WorkflowToolContext } from "./SoulToolsSection";
import { SoulFormBody } from "./SoulFormBody";
import { SoulFormFooter } from "./SoulFormFooter";
import { useSoulForm } from "./useSoulForm";

type WorkflowToolFile = {
  tools?: string[];
};

function buildBreadcrumbLabel(mode: "create" | "edit", role?: string | null) {
  if (mode === "create") {
    return "Souls > New Soul";
  }

  return `Souls > ${role ?? "Soul"} > Edit`;
}

function getWorkflowIdFromReturnUrl(returnUrl: string | null): string | null {
  if (!returnUrl) {
    return null;
  }

  const workflowMatch = returnUrl.match(/\/workflows\/([^/?#]+)(?:\/edit)?/);
  const workflowId = workflowMatch?.[1];
  return workflowId ? decodeURIComponent(workflowId) : null;
}

function buildWorkflowTools(
  yamlText: string | null | undefined,
  selectedTools: string[],
  availableTools: AvailableTool[],
): WorkflowToolContext[] {
  const filteredAvailableTools = availableTools.filter((tool) => tool.id !== "delegate");
  const availableToolMap = new Map(filteredAvailableTools.map((tool) => [tool.id, tool]));

  const fallbackTools = selectedTools
    .filter((tool) => tool !== "delegate")
    .map((tool) => ({
      id: tool,
      label: availableToolMap.get(tool)?.name ?? tool,
      description:
        availableToolMap.get(tool)?.description ??
        "Enabled on this soul. Open the form from a workflow to compare workflow tool availability.",
      enabled: true,
    }));

  if (!yamlText) {
    return fallbackTools;
  }

  try {
    const parsed = parse(yamlText) as WorkflowToolFile | null;
    const workflowToolIds = parsed?.tools;

    if (!Array.isArray(workflowToolIds)) {
      return fallbackTools;
    }

    const workflowTools = workflowToolIds
      .filter((toolId) => toolId !== "delegate")
      .map((toolId) => {
        const meta = availableToolMap.get(toolId);

        return {
          id: toolId,
          label: meta?.name ?? toolId,
          description: meta?.description ?? "Available in this workflow.",
          enabled: selectedTools.includes(toolId),
          availableInWorkflow: true,
        };
      });

    const knownToolIds = new Set(workflowTools.map((tool) => tool.id));
    const extraSelectedTools = selectedTools
      .filter((tool) => availableToolMap.has(tool) && !knownToolIds.has(tool))
      .map((tool) => ({
        id: tool,
        label: availableToolMap.get(tool)?.name ?? tool,
        description:
          availableToolMap.get(tool)?.description ??
          "Enabled on this soul, but not enabled in the current workflow.",
        enabled: true,
        availableInWorkflow: false,
      }));

    return [...workflowTools, ...extraSelectedTools];
  } catch {
    return fallbackTools;
  }
}

function SoulFormLoadingState({ returnUrl }: { returnUrl: string | null }) {
  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Edit Soul"
        subtitle="Loading..."
        breadcrumbs="Souls > Edit"
        backHref={returnUrl ?? "/souls"}
      />

      <div className="flex-1 overflow-y-auto pb-24">
        <div className="mx-auto flex w-full max-w-4xl flex-col gap-4 px-6 pb-8">
          {[1, 2, 3, 4].map((section) => (
            <div
              key={section}
              className="rounded-xl border border-border-default bg-surface-secondary p-5"
            >
              <div className="mb-4 h-5 w-32 animate-pulse rounded bg-border-default" />
              <div className="space-y-3">
                <div className="h-10 w-full animate-pulse rounded bg-border-default" />
                <div className="h-10 w-2/3 animate-pulse rounded bg-border-default" />
              </div>
            </div>
          ))}
        </div>
      </div>

      <footer className="sticky bottom-0 border-t border-[var(--border-subtle)] bg-[var(--surface-primary)]">
        <div className="mx-auto flex w-full max-w-4xl items-center justify-end gap-3 px-6 py-4">
          <div className="h-10 w-24 animate-pulse rounded bg-border-default" />
          <div className="h-10 w-32 animate-pulse rounded bg-border-default" />
        </div>
      </footer>
    </div>
  );
}

export function Component() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const returnUrl = searchParams.get("return");
  const workflowId = getWorkflowIdFromReturnUrl(returnUrl);
  const mode = id ? "edit" : "create";
  const soulQuery = useSoul(id ?? "");
  const availableToolsQuery = useAvailableTools();
  const workflowContext = useWorkflow(workflowId ?? "");

  const form = useSoulForm({
    mode,
    soulId: id,
    initial: soulQuery.data,
    onSuccess: () => {
      if (returnUrl) {
        navigate(returnUrl);
        return;
      }

      navigate("/souls");
    },
  });
  const { isDirty, isSubmitting, reset, setField, submit, values } = form;
  const workflowTools = buildWorkflowTools(
    workflowContext.data?.yaml,
    values.tools,
    availableToolsQuery.data ?? [],
  );

  useEffect(() => {
    if (mode === "edit" && soulQuery.data) {
      reset(soulQuery.data);
    }
  }, [mode, reset, soulQuery.data]);

  const blocker = useBlocker(isDirty && !isSubmitting);
  const isValid =
    values.name.trim().length > 0 && values.systemPrompt.trim().length > 0;

  if (mode === "edit" && soulQuery.isLoading) {
    return <SoulFormLoadingState returnUrl={returnUrl} />;
  }

  if (mode === "edit" && soulQuery.isError) {
    return (
      <div className="flex h-full flex-col">
        <PageHeader
          title="Soul not found"
          breadcrumbs="Souls > Edit"
          backHref="/souls"
        />
        <div className="px-6 text-sm text-muted">
          We could not load this soul.
        </div>
      </div>
    );
  }

  const pageTitle = mode === "create" ? "New Soul" : "Edit Soul";
  const breadcrumb = buildBreadcrumbLabel(mode, soulQuery.data?.role);

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title={pageTitle}
        breadcrumbs={breadcrumb}
        backHref={returnUrl ?? "/souls"}
      />

      <div className="flex-1 overflow-y-auto pb-24">
        <div className="mx-auto flex w-full max-w-4xl flex-col gap-4 px-6 pb-8">
          <SoulFormBody
            values={values}
            workflowTools={workflowTools}
            availableTools={availableToolsQuery.data ?? []}
            setField={setField}
          />
        </div>
      </div>

      <SoulFormFooter
        mode={mode}
        returnUrl={returnUrl}
        isDirty={isDirty}
        isSubmitting={isSubmitting}
        isValid={isValid}
        onCancel={() => navigate(returnUrl ?? "/souls")}
        onSubmit={() => {
          void submit();
        }}
      />

      <Dialog open={blocker.state === "blocked"}>
        <DialogContent>
          <DialogTitle>Unsaved changes</DialogTitle>
          <p className="px-5 py-4 text-sm text-muted">
            You have unsaved changes that will be lost if you leave this page.
          </p>
          <DialogFooter>
            <Button variant="ghost" onClick={() => blocker.reset?.()}>
              Keep editing
            </Button>
            <Button variant="secondary" onClick={() => blocker.proceed?.()}>
              Discard changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
