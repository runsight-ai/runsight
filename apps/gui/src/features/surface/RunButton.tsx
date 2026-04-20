import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { Button } from "@runsight/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@runsight/ui/tooltip";
import { useCreateRun, useCancelRun, useRun } from "@/queries/runs";
import { useWorkflow } from "@/queries/workflows";
import { useProviders } from "@/queries/settings";
import { useCanvasStore } from "@/store/canvas";
import { gitApi } from "@/api/git";
import type { WorkflowResponse } from "@runsight/shared/zod";
import { Play, X, Key } from "lucide-react";
import { resolveRunInputSchemaDecision } from "./runInputSchemaPolicy";

interface RunButtonProps {
  workflowId: string;
  isCommitted?: boolean;
  onAddApiKey?: () => void;
}

type RunSource = "manual" | "simulation";
type WorkflowInputSchema = NonNullable<WorkflowResponse["input_schema"]>;
type RunInputsModalComponent = typeof import("./RunInputsModal")["RunInputsModal"];
type PendingRun = {
  source: RunSource;
  branch: string;
  workflow: {
    id: string;
    name?: WorkflowResponse["name"];
    commit_sha?: WorkflowResponse["commit_sha"];
    branch?: string;
    input_schema: WorkflowInputSchema;
  };
};

let runInputsModalPromise: Promise<{ RunInputsModal: RunInputsModalComponent }> | null = null;
let runInputsModalComponentCache: RunInputsModalComponent | null = null;

export function RunButton({ workflowId, isCommitted = true, onAddApiKey }: RunButtonProps) {
  if (typeof window === "undefined") {
    return (
      <RunButtonContent
        workflowId={workflowId}
        workflow={undefined}
        isCommitted={isCommitted}
        onAddApiKey={onAddApiKey}
      />
    );
  }

  return (
    <WorkflowDataFetcher workflowId={workflowId}>
      {(workflow) => (
        <RunButtonContent
          workflowId={workflowId}
          workflow={workflow}
          isCommitted={isCommitted}
          onAddApiKey={onAddApiKey}
        />
      )}
    </WorkflowDataFetcher>
  );
}

function RunButtonContent({
  workflowId,
  workflow,
  isCommitted = true,
  onAddApiKey,
}: {
  workflowId: string;
  workflow?: WorkflowResponse;
  isCommitted?: boolean;
  onAddApiKey?: () => void;
}) {
  const navigate = useNavigate();
  const activeRunId = useCanvasStore((s) => s.activeRunId);
  const setActiveRunId = useCanvasStore((s) => s.setActiveRunId);
  const nodes = useCanvasStore((s) => s.nodes);
  const blockCount = useCanvasStore((s) => s.blockCount);
  const isDirty = useCanvasStore((s) => s.isDirty);
  const yamlContent = useCanvasStore((s) => s.yamlContent);

  const { data: providers } = useProviders();
  const activeProviders = (providers?.items ?? []).filter((provider) => provider.is_active ?? true);
  const hasProviders = activeProviders.length > 0;

  const createRun = useCreateRun();
  const cancelRun = useCancelRun();
  const RunInputsModal = useRunInputsModal(workflow);
  const [isRunInputsModalOpen, setIsRunInputsModalOpen] = useState(false);
  const [pendingRun, setPendingRun] = useState<PendingRun | null>(null);
  const [isPreparingRun, setIsPreparingRun] = useState(false);

  const { data: run } = useRun(activeRunId ?? "", {
    refetchInterval: activeRunId ? 2000 : false,
  });

  const status = run?.status;
  const isRunning = activeRunId && status === "running";
  const hasYamlContent = yamlContent.trim().length > 0;

  useEffect(() => {
    if (activeRunId && (status === "completed" || status === "failed" || status === "cancelled")) {
      setActiveRunId(null);
    }
  }, [activeRunId, status, setActiveRunId]);

  const isEmpty = !hasYamlContent && !nodes.length && !blockCount;
  const isPending = createRun.isPending || cancelRun.isPending || isPreparingRun;
  const shouldRunOnSimulation = isDirty || !isCommitted;

  function getRunWorkflowSchema() {
    if (workflow && workflow.id === workflowId) {
      return workflow.input_schema ?? null;
    }

    return null;
  }

  function openInputsModal(
    decision: Extract<
      Awaited<ReturnType<typeof resolveRunInputSchemaDecision>>,
      { kind: "needs_inputs" }
    >,
    source: RunSource,
  ) {
    setPendingRun({
      source,
      branch: decision.branch ?? "main",
      workflow: {
        id: workflow?.id ?? workflowId,
        name: workflow?.name,
        commit_sha: decision.commit_sha,
        branch: decision.branch ?? "main",
        input_schema: decision.input_schema,
      },
    });
    setIsRunInputsModalOpen(true);
  }

  function closeInputsModal(nextOpen: boolean) {
    setIsRunInputsModalOpen(nextOpen);
    if (!nextOpen) {
      setPendingRun(null);
    }
  }

  function submitRun(inputs: Record<string, unknown>, source: RunSource, branch: string) {
    return new Promise<void>((resolve, reject) => {
      try {
        createRun.mutate(
          {
            workflow_id: workflowId,
            inputs,
            source,
            branch,
          },
          {
            onSuccess: (result) => {
              setActiveRunId(result.id);
              navigate(`/runs/${result.id}`);
              resolve();
            },
          },
        );
      } catch (error) {
        reject(error);
      }
    });
  }

  async function handleClick() {
    if (isRunning) {
      cancelRun.mutate(activeRunId);
      return;
    }

    const workflowInputSchema = getRunWorkflowSchema();

    if (!shouldRunOnSimulation) {
      if (workflowInputSchema && Object.keys(workflowInputSchema).length > 0) {
        setPendingRun({
          source: "manual",
          branch: "main",
          workflow: {
            id: workflow?.id ?? workflowId,
            name: workflow?.name,
            commit_sha: workflow?.commit_sha,
            branch: "main",
            input_schema: workflowInputSchema,
          },
        });
        setIsRunInputsModalOpen(true);
        return;
      }

      void submitRun({}, "manual", "main").catch((error) => {
        toast.error("Unable to start run", {
          description: error instanceof Error ? error.message : "Run failed.",
        });
      });
      return;
    }

    setIsPreparingRun(true);
    try {
      const decision = await resolveRunInputSchemaDecision({
        workflow: {
          id: workflow?.id ?? workflowId,
          input_schema: workflowInputSchema,
        },
        isDirty: true,
        yamlContent,
        prepareSimulation: gitApi.createSimBranch,
      });

      if (decision.kind === "blocked") {
        toast.error("Unable to start run", { description: decision.error.message });
        return;
      }

      const source: RunSource = decision.branch ? "simulation" : "manual";
      const branch = decision.branch ?? "main";

      if (decision.kind === "needs_inputs") {
        openInputsModal(decision, source);
        return;
      }

      void submitRun({}, source, branch);
    } catch (error) {
      toast.error("Unable to start run", {
        description: error instanceof Error ? error.message : "Run failed.",
      });
    } finally {
      setIsPreparingRun(false);
    }
  }

  if (!hasProviders && !isRunning) {
    return (
      <Button
        variant="primary"
        onClick={() => onAddApiKey?.()}
        data-testid="workflow-add-api-key-button"
      >
        <Key className="size-4" />
        Add API Key
      </Button>
    );
  }

  const button = (
    <Button
      variant={isRunning ? "danger" : "primary"}
      disabled={isEmpty && !isRunning}
      loading={isPending}
      onClick={handleClick}
      data-testid="workflow-run-button"
    >
      {isRunning ? (
        <>
          <X className="size-4" />
          Cancel
        </>
      ) : (
        <>
          <Play className="size-4" />
          Run
        </>
      )}
    </Button>
  );

  if (isEmpty && !isRunning) {
    return (
      <>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger render={button} />
            <TooltipContent>Add at least one block</TooltipContent>
          </Tooltip>
        </TooltipProvider>
        {RunInputsModal ? (
          <RunInputsModalSlot
            RunInputsModal={RunInputsModal}
            workflow={workflow}
            workflowId={workflowId}
            pendingRun={pendingRun}
            open={isRunInputsModalOpen}
            submitting={createRun.isPending}
            onOpenChange={closeInputsModal}
            onSubmit={submitRun}
          />
        ) : null}
      </>
    );
  }

  return (
    <>
      {button}
      {RunInputsModal ? (
        <RunInputsModalSlot
          RunInputsModal={RunInputsModal}
          workflow={workflow}
          workflowId={workflowId}
          pendingRun={pendingRun}
          open={isRunInputsModalOpen}
          submitting={createRun.isPending}
          onOpenChange={closeInputsModal}
          onSubmit={submitRun}
        />
      ) : null}
    </>
  );
}

function RunInputsModalSlot({
  RunInputsModal,
  workflow,
  workflowId,
  pendingRun,
  open,
  submitting,
  onOpenChange,
  onSubmit,
}: {
  RunInputsModal: RunInputsModalComponent;
  workflow?: WorkflowResponse;
  workflowId: string;
  pendingRun: PendingRun | null;
  open: boolean;
  submitting: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (
    inputs: Record<string, unknown>,
    source: RunSource,
    branch: string,
  ) => Promise<void>;
}) {
  return (
    <RunInputsModal
      open={open}
      workflow={
        pendingRun?.workflow ?? {
          id: workflow?.id ?? workflowId,
          name: workflow?.name,
          input_schema: workflow?.input_schema ?? null,
        }
      }
      submitting={submitting}
      onOpenChange={onOpenChange}
      onSubmit={(inputs) => {
        if (!pendingRun) {
          return Promise.reject(new Error("Run inputs are unavailable."));
        }

        return onSubmit(inputs, pendingRun.source, pendingRun.branch);
      }}
    />
  );
}

function useRunInputsModal(workflow?: WorkflowResponse) {
  const [component, setComponent] = useState<RunInputsModalComponent | null>(() =>
    getRunInputsModalComponent(workflow),
  );

  useEffect(() => {
    if (!workflow || component) {
      return;
    }

    let cancelled = false;
    void getRunInputsModalPromise().then((module) => {
      if (!cancelled) {
        runInputsModalComponentCache = module.RunInputsModal;
        setComponent(() => module.RunInputsModal);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [component, workflow]);

  return component;
}

function getRunInputsModalPromise() {
  if (!runInputsModalPromise) {
    runInputsModalPromise = import("./RunInputsModal");
  }

  return runInputsModalPromise;
}

function getRunInputsModalComponent(workflow?: WorkflowResponse) {
  if (!workflow) {
    return null;
  }

  if (runInputsModalComponentCache) {
    return runInputsModalComponentCache;
  }

  try {
    const requireFn = Function("return require")() as
      | ((id: string) => { RunInputsModal: RunInputsModalComponent })
      | undefined;

    runInputsModalComponentCache = requireFn?.("./RunInputsModal").RunInputsModal ?? null;
    return runInputsModalComponentCache;
  } catch {
    return null;
  }
}

function WorkflowDataFetcher({
  workflowId,
  children,
}: {
  workflowId: string;
  children: (workflow?: WorkflowResponse) => ReactNode;
}) {
  const workflowQuery = useWorkflow(workflowId);
  return <>{children(workflowQuery.data)}</>;
}
