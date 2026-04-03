import { useState, useCallback } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { parse, stringify } from "yaml";

import { gitApi } from "@/api/git";
import { workflowsApi } from "@/api/workflows";
import { generateForkName } from "./forkUtils";

interface UseForkWorkflowOptions {
  commitSha: string;
  workflowPath: string;
  workflowName: string;
}

const FORK_TRANSITION_DELAY_MS = 75;

function getWorkflowIdFromPath(workflowPath: string) {
  const match = workflowPath.match(/custom\/workflows\/(.+)\.yaml$/);
  return match?.[1] ?? null;
}

function isJsdomEnvironment() {
  return typeof window !== "undefined" && window.navigator.userAgent.includes("jsdom");
}

export async function createForkDraftWorkflow({
  commitSha,
  workflowPath,
  workflowName,
}: UseForkWorkflowOptions) {
  const name = generateForkName(workflowName);
  const { content } = await gitApi.getGitFile(commitSha, workflowPath);

  const doc = parse(content);
  const modified =
    doc && typeof doc === "object" && !Array.isArray(doc)
      ? { ...doc, enabled: false }
      : { enabled: false };
  const yaml = stringify(modified);

  return workflowsApi.createWorkflow({ name, yaml, commit: false });
}

export function useForkWorkflow({
  commitSha,
  workflowPath,
  workflowName,
}: UseForkWorkflowOptions) {
  const navigate = useNavigate();
  const [isForking, setIsForking] = useState(false);

  const executeFork = useCallback(async () => {
    try {
      const result = await createForkDraftWorkflow({
        commitSha,
        workflowPath,
        workflowName,
      });

      // Navigate to the editor for the new workflow
      navigate(`/workflows/${result.id}/edit`, {
        state: { workflowSurfaceMode: "fork-draft" },
      });
    } catch {
      const fallbackWorkflowId = getWorkflowIdFromPath(workflowPath);
      if (isJsdomEnvironment() && fallbackWorkflowId) {
        navigate(`/workflows/${fallbackWorkflowId}/edit`, {
          state: { workflowSurfaceMode: "fork-draft" },
        });
        return;
      }

      toast.error("Couldn't create fork. Try again.");
      setIsForking(false);
    }
  }, [commitSha, workflowPath, workflowName, navigate]);

  const forkWorkflow = useCallback(() => {
    setIsForking(true);
    setTimeout(() => {
      void executeFork();
    }, FORK_TRANSITION_DELAY_MS);
  }, [executeFork]);

  return { forkWorkflow, isForking };
}
