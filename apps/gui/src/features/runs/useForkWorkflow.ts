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

export function useForkWorkflow({
  commitSha,
  workflowPath,
  workflowName,
}: UseForkWorkflowOptions) {
  const navigate = useNavigate();
  const [isForking, setIsForking] = useState(false);

  const executeFork = useCallback(async () => {
    const name = generateForkName(workflowName);

    try {
      // Read YAML at the commit snapshot
      const { content } = await gitApi.getGitFile(commitSha, workflowPath);

      // Parse YAML and set enabled: false
      const doc = parse(content);
      const modified =
        doc && typeof doc === "object" && !Array.isArray(doc)
          ? { ...doc, enabled: false }
          : { enabled: false };
      const yaml = stringify(modified);

      // Create the new draft workflow
      const result = await workflowsApi.createWorkflow({ name, yaml });

      // Navigate to the editor for the new workflow
      navigate(`/workflows/${result.id}/edit`);
    } catch {
      toast.error("Couldn't create fork. Try again.");
      // Navigate to draft even on error so the user can retry from the editor
      navigate(`/workflows/${name}/edit`);
      setIsForking(false);
    }
  }, [commitSha, workflowPath, workflowName, navigate]);

  const forkWorkflow = useCallback(() => {
    setIsForking(true);
    // Schedule the fork after the next paint so the "Forking..." label
    // is visible before the network round-trip begins.
    requestAnimationFrame(() => void executeFork());
  }, [executeFork]);

  return { forkWorkflow, isForking };
}
