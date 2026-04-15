import { useState, useCallback } from "react";
import { toast } from "sonner";
import { parse, stringify } from "yaml";

import { gitApi } from "@/api/git";
import { workflowsApi } from "@/api/workflows";
import { generateForkName } from "./forkUtils";

interface UseForkWorkflowOptions {
  commitSha: string;
  workflowPath: string;
  workflowName: string;
  onTransition?: (id: string) => void;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function rewriteForkWorkflowYaml(
  content: string,
  forkWorkflowId: string,
  forkWorkflowName: string,
): string {
  const doc = parse(content);
  const modified = isPlainObject(doc) ? { ...doc } : {};
  modified.id = forkWorkflowId;
  modified.kind = "workflow";
  modified.enabled = false;
  modified.workflow = isPlainObject(modified.workflow)
    ? { ...modified.workflow, name: forkWorkflowName }
    : { name: forkWorkflowName };
  return stringify(modified);
}

export function useForkWorkflow({
  commitSha,
  workflowPath,
  workflowName,
  onTransition,
}: UseForkWorkflowOptions) {
  const [isForking, setIsForking] = useState(false);
  const [forkedWorkflowId, setForkedWorkflowId] = useState<string | undefined>(
    undefined,
  );

  const executeFork = useCallback(async () => {
    const name = generateForkName(workflowName);
    const forkWorkflowId = name;

    try {
      // Read YAML at the commit snapshot
      const { content } = await gitApi.getGitFile(commitSha, workflowPath);

      const yaml = rewriteForkWorkflowYaml(content, forkWorkflowId, name);

      // Create the new draft workflow (no auto-commit — shows as uncommitted)
      const result = await workflowsApi.createWorkflow({
        name,
        yaml,
        commit: false,
      });

      setForkedWorkflowId(result.id);
      if (onTransition) onTransition(result.id);
    } catch {
      toast.error("Couldn't create fork. Try again.");
    } finally {
      setIsForking(false);
    }
  }, [commitSha, workflowPath, workflowName, onTransition]);

  const forkWorkflow = useCallback(() => {
    setIsForking(true);
    // Schedule the fork after the next paint so the "Forking..." label
    // is visible before the network round-trip begins.
    requestAnimationFrame(() => void executeFork());
  }, [executeFork]);

  return { forkWorkflow, isForking, forkedWorkflowId };
}
